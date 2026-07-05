"""
Safety Agent
------------
Acts as a hard checkpoint between the user and the Scheduler Agent's
output. Its only job is to detect when a request crosses from
"logistics" (scheduling, reminders, refills) into "clinical advice"
(diagnosis, dosing judgment, drug-interaction judgment) and, if so,
intercept with a bounded, honest redirect.

Design principle: this agent is deliberately narrow and conservative.
It does NOT try to give a "softer" partial medical answer. It names
the concern, states plainly that it cannot give medical advice, and
routes the user to a pharmacist or physician.
"""

from dataclasses import dataclass
from typing import Optional
import re

# Keyword/phrase patterns that indicate a request is asking for
# clinical judgment rather than scheduling help. This is intentionally
# a simple, auditable rule-based first pass -- in production this
# would be backed by a classifier and/or a licensed drug-interaction
# API (see README "What's Next").
CLINICAL_ADVICE_PATTERNS = [
    r"\bcan i take\b.*\bwith\b",
    r"\bis it safe to\b",
    r"\bshould i take\b",
    r"\bwhat dose\b",
    r"\bhow much\b.*\bshould\b",
    r"\bdrug interaction\b",
    r"\bside effect\b",
    r"\bdiagnos",
    r"\bstop taking\b",
    r"\bskip (a|my|the) dose\b",
]

# Known high-risk interaction pairs used only to make the flag
# MORE specific when we can -- never to approve a combination.
KNOWN_RISK_HINTS = {
    frozenset({"ibuprofen", "lisinopril"}): (
        "NSAIDs like ibuprofen can reduce the effectiveness of ACE "
        "inhibitors like lisinopril and may affect kidney function."
    ),
    frozenset({"aspirin", "warfarin"}): (
        "Combining aspirin with warfarin can increase bleeding risk."
    ),
}


@dataclass
class SafetyCheckResult:
    blocked: bool
    reason: Optional[str] = None
    user_message: Optional[str] = None


class SafetyAgent:
    """Guardrail agent. Runs on every user turn before the Scheduler
    Agent's response is finalized."""

    def __init__(self, known_medications: Optional[list[str]] = None):
        self.known_medications = known_medications or []

    def check(self, user_text: str) -> SafetyCheckResult:
        text = user_text.lower()

        if not any(re.search(p, text) for p in CLINICAL_ADVICE_PATTERNS):
            return SafetyCheckResult(blocked=False)

        # Try to make the flag specific if we recognize a known pair
        mentioned = {m for m in self.known_medications if m.lower() in text}
        hint = None
        for pair, explanation in KNOWN_RISK_HINTS.items():
            if pair.issubset({m.lower() for m in mentioned}):
                hint = explanation
                break

        message = self._build_redirect_message(hint)
        return SafetyCheckResult(
            blocked=True,
            reason="clinical_advice_requested",
            user_message=message,
        )

    @staticmethod
    def _build_redirect_message(hint: Optional[str]) -> str:
        base = (
            "I can't provide medical advice, dosing guidance, or an "
            "interaction judgment -- that requires a pharmacist or "
            "physician who knows your full medical history."
        )
        if hint:
            base = f"Possible concern: {hint} {base}"
        return base + " Please check with your pharmacist or doctor before proceeding."


if __name__ == "__main__":
    agent = SafetyAgent(known_medications=["ibuprofen", "lisinopril", "metformin"])
    result = agent.check("Can I take ibuprofen with lisinopril for a headache?")
    print(result)
