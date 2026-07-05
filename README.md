# CareLoop — A Safety-First Concierge Agent for Medication Management

Built for the **AI Agents: Intensive Vibe Coding Capstone Project** (Concierge Agents track).

CareLoop is a multi-agent system that helps people manage medication schedules, refills, and doctor-visit prep through natural conversation — while enforcing a hard boundary around medical advice via a dedicated Safety Agent.

## Problem

Roughly half of patients with chronic conditions don't take medication exactly as prescribed. Existing pill-reminder apps are dumb timers — they don't understand context, flag risks, or produce anything useful for a doctor's appointment. CareLoop is a conversational concierge that does, without ever pretending to be a clinician.

## Architecture

```
User → Scheduler Agent (ADK + Gemini reasoning) → Safety Agent checkpoint
                    ↓                                      ↓
              MCP Server (persistent schedule/adherence store)
                    ↓
                 Output (reminders, refill flags, adherence report)
```

- **`agents/scheduler_agent.py`** — parses medication text, manages schedule entries, calculates refills, builds the adherence report. Built as an ADK-style tool-calling agent.
- **`agents/safety_agent.py`** — the guardrail. Runs on every user turn *before* the Scheduler Agent's response is finalized. Detects clinical-advice requests and redirects to a pharmacist/physician instead of answering.
- **`mcp_server/`** — exposes schedule storage as MCP tools (`add_medication`, `list_medications`, `log_dose_taken`, `get_adherence_summary`), so the same data store is reusable by any MCP-compatible client, not just this app.
- **`demo.py`** — runs the full flow end-to-end with no API key required.

## Why two agents instead of one

Scheduling logistics and safety enforcement have different failure modes. A scheduling mistake is an inconvenience; a safety-boundary mistake is a harm vector. Keeping them as separate agents means the Safety Agent stays narrow and conservative even as the Scheduler Agent's conversational flexibility improves — one doesn't get more permissive by accident when the other gets smarter.

## Security & privacy

- No raw PII (names, emails) is ever stored — only medication schedule data keyed by a random local entry ID.
- API keys are loaded from environment variables only (`GEMINI_API_KEY`), never committed. See `.gitignore`.
- The Safety Agent is architecturally separate from the main reasoning loop, so it's auditable and testable independently.

## Course concepts demonstrated

| Concept | Where |
|---|---|
| Multi-agent system (ADK) | `agents/scheduler_agent.py`, `agents/safety_agent.py` |
| MCP Server | `mcp_server/server.py`, `mcp_server/client.py` |
| Security features | No-PII storage, env-based secrets, isolated guardrail agent |
| Agent skills | Medication scheduling packaged as a portable, reusable skill |
| Antigravity | Used during development; see writeup for details |
| Deployability | Services are independently containerizable; see below |

## Setup

```bash
git clone <your-repo-url>
cd careloop
pip install -r requirements.txt

# Run the demo (no API key needed — uses rule-based parsing)
python3 demo.py

# Run tests
pytest tests/ -v

# (Optional) Run the MCP server standalone
export GEMINI_API_KEY=your_key_here   # only needed for live NLU parsing
python3 -m mcp_server.server
```

## What's next

1. Multi-user / caregiver mode with access boundaries
2. Real drug-interaction data source (licensed pharmacological API) behind the Safety Agent, replacing the current rule-based pattern matching
3. Voice input for the target user base

## Disclaimer

CareLoop is a scheduling and logistics tool. It is not a medical device and does not provide diagnosis, treatment, or dosing advice. Always consult a licensed pharmacist or physician for medical decisions.
