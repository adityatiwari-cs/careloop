"""
MCP Server entrypoint.

Wires the schedule/adherence storage in client.py up as MCP tools
using the official `mcp` Python SDK, so any MCP-compatible client
(Claude, Antigravity, a custom caregiver dashboard, etc.) can call
into CareLoop's schedule store directly.

Run with:
    pip install mcp
    python -m mcp_server.server

Then point an MCP client's config at this server, e.g.:
    {
      "mcpServers": {
        "careloop-schedule": {
          "command": "python",
          "args": ["-m", "mcp_server.server"]
        }
      }
    }
"""

from mcp.server.fastmcp import FastMCP
from mcp_server.client import MCPScheduleClient

mcp = FastMCP("careloop-schedule")
_store = MCPScheduleClient()


@mcp.tool()
def add_medication(medication: str, dose: str, times_per_day: int, time_of_day: list[str], days_supply: int = 30) -> dict:
    """Add a medication schedule entry."""
    class _Entry:
        pass
    e = _Entry()
    e.medication, e.dose, e.times_per_day = medication, dose, times_per_day
    e.time_of_day, e.days_supply = time_of_day, days_supply
    from datetime import datetime
    e.start_date = datetime.utcnow().date().isoformat()
    return _store.save_entry(e)


@mcp.tool()
def list_medications() -> list[dict]:
    """List all currently scheduled medications."""
    return _store.list_entries()


@mcp.tool()
def log_dose_taken(medication: str, time_of_day: str, taken: bool) -> dict:
    """Log whether a dose was taken at a given time slot."""
    return _store.log_dose(medication, time_of_day, taken)


@mcp.tool()
def get_adherence_summary(days: int = 14) -> list[dict]:
    """Retrieve the raw adherence log for the last N days."""
    return _store.get_adherence_log(days=days)


if __name__ == "__main__":
    mcp.run()
