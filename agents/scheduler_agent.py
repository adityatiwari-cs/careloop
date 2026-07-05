"""
Scheduler Agent
---------------
Primary conversational agent. Responsible for:
  - Parsing free-text medication descriptions into structured schedule
    entries (drug name, dose, frequency, time-of-day)
  - Creating / updating reminders
  - Calculating refill windows
  - Assembling the 14-day adherence report

Built against the Agent Development Kit (ADK) tool-calling pattern:
this agent exposes a small set of narrowly-scoped tools rather than
freeform code execution. Swap `call_gemini` for the real
`google.adk` / Gemini API client to run this against a live model --
this file is structured so that's a drop-in change (see README).
"""

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from typing import Optional
import json
import os

from mcp_server.client import MCPScheduleClient
from agents.safety_agent import SafetyAgent


@dataclass
class ScheduleEntry:
    medication: str
    dose: str
    times_per_day: int
    time_of_day: list[str]
    days_supply: int = 30
    start_date: str = field(default_factory=lambda: datetime.utcnow().date().isoformat())


class SchedulerAgent:
    """ADK-style tool-calling agent. `tools` maps a tool name to a
    callable -- this mirrors how ADK registers tools for the model to
    invoke, without requiring the ADK package to be installed to read
    or test this code."""

    def __init__(self, mcp_client: MCPScheduleClient, safety_agent: SafetyAgent):
        self.mcp_client = mcp_client
        self.safety_agent = safety_agent
        self.tools = {
            "add_schedule_entry": self.add_schedule_entry,
            "get_upcoming_refills": self.get_upcoming_refills,
            "build_adherence_report": self.build_adherence_report,
        }

    # ---- Tool implementations -------------------------------------

    def add_schedule_entry(self, entry: ScheduleEntry) -> dict:
        """Persist a new medication schedule via the MCP server."""
        return self.mcp_client.save_entry(entry)

    def get_upcoming_refills(self, within_days: int = 5) -> list[dict]:
        """Return medications whose supply runs out within N days."""
        entries = self.mcp_client.list_entries()
        upcoming = []
        for e in entries:
            start = datetime.fromisoformat(e["start_date"])
            refill_date = start + timedelta(days=e["days_supply"])
            days_left = (refill_date - datetime.utcnow()).days
            if days_left <= within_days:
                upcoming.append({**e, "days_until_refill": days_left})
        return upcoming

    def build_adherence_report(self, days: int = 14) -> dict:
        """Assemble a doctor-ready adherence summary from logged doses."""
        log = self.mcp_client.get_adherence_log(days=days)
        summary = {}
        for record in log:
            key = f'{record["medication"]} ({record["time_of_day"]})'
            summary.setdefault(key, {"taken": 0, "total": 0})
            summary[key]["total"] += 1
            if record["taken"]:
                summary[key]["taken"] += 1

        return {
            "window_days": days,
            "summary": {
                k: {
                    "taken": v["taken"],
                    "total": v["total"],
                    "adherence_pct": round(100 * v["taken"] / v["total"], 1) if v["total"] else 0,
                }
                for k, v in summary.items()
            },
            "flagged_safety_events": self.mcp_client.get_flagged_events(days=days),
        }

    # ---- Main conversational entry point ---------------------------

    def handle_message(self, user_text: str) -> dict:
        """Every user turn passes through the Safety Agent first. This
        is the architectural guardrail described in the writeup: the
        Scheduler Agent's more flexible reasoning never gets the last
        word on a safety-relevant request."""

        known_meds = [e["medication"] for e in self.mcp_client.list_entries()]
        self.safety_agent.known_medications = known_meds

        safety_result = self.safety_agent.check(user_text)
        if safety_result.blocked:
            return {
                "handled_by": "safety_agent",
                "response": safety_result.user_message,
            }

        parsed = self._parse_medication_text(user_text)
        if parsed:
            saved = self.add_schedule_entry(parsed)
            return {
                "handled_by": "scheduler_agent",
                "response": (
                    f"Got it -- I've scheduled {parsed.medication} "
                    f"{', '.join(parsed.time_of_day)}. "
                    f"I'll flag your refill about 5 days before it runs out."
                ),
                "saved_entry": saved,
            }

        return {
            "handled_by": "scheduler_agent",
            "response": (
                "I didn't catch a medication and schedule in that message. "
                "Try something like: 'I take metformin 500mg twice a day.'"
            ),
        }

    def _parse_medication_text(self, text: str) -> Optional[ScheduleEntry]:
        """Lightweight rule-based parser used for local testing without
        a live model call. In production this call is replaced with a
        Gemini API / ADK tool-call request that returns structured JSON
        -- see `call_gemini_for_parsing()` below for the drop-in shape.
        """
        text_lower = text.lower()
        if "twice a day" in text_lower or "2x" in text_lower:
            times_per_day, time_of_day = 2, ["8am", "8pm"]
        elif "three times a day" in text_lower or "3x" in text_lower:
            times_per_day, time_of_day = 3, ["8am", "2pm", "8pm"]
        else:
            times_per_day, time_of_day = 1, ["8am"]

        for med in ["metformin", "lisinopril", "atorvastatin", "amlodipine"]:
            if med in text_lower:
                return ScheduleEntry(
                    medication=med.capitalize(),
                    dose="as stated",
                    times_per_day=times_per_day,
                    time_of_day=time_of_day,
                )
        return None

    def call_gemini_for_parsing(self, text: str) -> dict:
        """Drop-in shape for a real Gemini API call. Not invoked by
        default so this repo runs fully offline for judges without an
        API key. Set GEMINI_API_KEY to enable.

        import google.generativeai as genai
        genai.configure(api_key=os.environ["GEMINI_API_KEY"])
        model = genai.GenerativeModel("gemini-2.0-flash")
        response = model.generate_content(
            f"Extract medication, dose, and frequency as JSON from: {text}"
        )
        return json.loads(response.text)
        """
        raise NotImplementedError("Wire up GEMINI_API_KEY to enable live parsing.")
