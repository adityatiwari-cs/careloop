"""
demo.py -- Run this to see CareLoop end-to-end without any API key.

    python3 demo.py

This is the exact flow shown in the product-walkthrough screenshot:
scheduling a medication, then asking an interaction question that
gets intercepted by the Safety Agent, then generating an adherence
report.

Set GEMINI_API_KEY in your environment to swap the rule-based parser
for live Gemini-powered natural language parsing (see
agents/scheduler_agent.py -> call_gemini_for_parsing).
"""

import os
import tempfile

os.environ.setdefault("CARELOOP_DATA_DIR", tempfile.mkdtemp())

from agents.safety_agent import SafetyAgent
from agents.scheduler_agent import SchedulerAgent
from mcp_server.client import MCPScheduleClient


def main():
    client = MCPScheduleClient()
    safety = SafetyAgent()
    agent = SchedulerAgent(mcp_client=client, safety_agent=safety)

    conversation = [
        "I take metformin 500mg twice a day",
        "I also take lisinopril in the morning",
        "Can I take ibuprofen with lisinopril for a headache?",
    ]

    print("=" * 60)
    print("CareLoop Demo -- Multi-Agent Medication Concierge")
    print("=" * 60)

    for user_text in conversation:
        print(f"\nUser: {user_text}")
        result = agent.handle_message(user_text)
        print(f"[{result['handled_by']}]: {result['response']}")

    # Simulate two weeks of logged doses for the report
    client.log_dose("Metformin", "8am", True)
    client.log_dose("Metformin", "8pm", False)
    client.log_dose("Lisinopril", "8am", True)

    print("\n" + "=" * 60)
    print("14-Day Adherence Report")
    print("=" * 60)
    report = agent.build_adherence_report(days=14)
    for med, stats in report["summary"].items():
        print(f"  {med}: {stats['taken']}/{stats['total']} ({stats['adherence_pct']}%)")

    print(f"\nFlagged safety events in window: {len(report['flagged_safety_events'])}")


if __name__ == "__main__":
    main()
