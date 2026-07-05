"""
MCP Server -- Schedule Persistence
-----------------------------------
Exposes medication schedule storage, refill tracking, and adherence
logging as MCP tools, so any MCP-compatible client (this app, a
calendar integration, a future caregiver dashboard) can read/write
the same schedule state without depending on CareLoop's internal code.

This file implements the storage logic directly. `server.py` (below)
wires these methods up as MCP tool handlers using the `mcp` Python
SDK's server primitives.
"""

import json
import os
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

DATA_DIR = Path(os.environ.get("CARELOOP_DATA_DIR", Path(__file__).parent.parent / "data"))
DATA_DIR.mkdir(exist_ok=True)

SCHEDULE_FILE = DATA_DIR / "schedule.json"
ADHERENCE_FILE = DATA_DIR / "adherence_log.json"
SAFETY_EVENTS_FILE = DATA_DIR / "safety_events.json"


def _load(path: Path) -> list:
    if not path.exists():
        return []
    with open(path) as f:
        return json.load(f)


def _save(path: Path, data: list) -> None:
    with open(path, "w") as f:
        json.dump(data, f, indent=2)


class MCPScheduleClient:
    """Client interface used by the Scheduler Agent. In a full MCP
    deployment this class's methods are what the MCP server exposes
    as tools (see server.py) -- kept as a plain class here so the
    logic is directly unit-testable without spinning up a server.

    IMPORTANT: no direct identifiers (names, emails) are ever stored
    here -- only medication schedule data, keyed by a random local
    entry id. This is the "zero raw PII" boundary referenced in the
    writeup.
    """

    def save_entry(self, entry) -> dict:
        entries = _load(SCHEDULE_FILE)
        record = {
            "id": str(uuid.uuid4())[:8],
            "medication": entry.medication,
            "dose": entry.dose,
            "times_per_day": entry.times_per_day,
            "time_of_day": entry.time_of_day,
            "days_supply": entry.days_supply,
            "start_date": entry.start_date,
        }
        entries.append(record)
        _save(SCHEDULE_FILE, entries)
        return record

    def list_entries(self) -> list[dict]:
        return _load(SCHEDULE_FILE)

    def log_dose(self, medication: str, time_of_day: str, taken: bool, when: Optional[str] = None) -> dict:
        log = _load(ADHERENCE_FILE)
        record = {
            "medication": medication,
            "time_of_day": time_of_day,
            "taken": taken,
            "timestamp": when or datetime.utcnow().isoformat(),
        }
        log.append(record)
        _save(ADHERENCE_FILE, log)
        return record

    def get_adherence_log(self, days: int = 14) -> list[dict]:
        log = _load(ADHERENCE_FILE)
        cutoff = datetime.utcnow() - timedelta(days=days)
        return [r for r in log if datetime.fromisoformat(r["timestamp"]) >= cutoff]

    def log_safety_event(self, category: str, note: str) -> dict:
        events = _load(SAFETY_EVENTS_FILE)
        record = {
            "category": category,
            "note": note,
            "timestamp": datetime.utcnow().isoformat(),
        }
        events.append(record)
        _save(SAFETY_EVENTS_FILE, events)
        return record

    def get_flagged_events(self, days: int = 14) -> list[dict]:
        events = _load(SAFETY_EVENTS_FILE)
        cutoff = datetime.utcnow() - timedelta(days=days)
        return [e for e in events if datetime.fromisoformat(e["timestamp"]) >= cutoff]
