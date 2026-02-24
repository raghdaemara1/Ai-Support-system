import os
import re

from app.models.agent_models import Session


class EscalationEngine:
    """Rules-first escalation engine."""

    HARD_ESCALATE = re.compile(
        r"\b(fire|smoke|injury|emergency|explosion|danger|critical|production stop|urgent|unsafe|shutdown)\b",
        re.IGNORECASE,
    )
    AGENT_UNSURE = re.compile(
        r"(don't know|cannot find|not sure|no information|unclear|consult)",
        re.IGNORECASE,
    )

    def should_escalate(self, message: str, response: str, session: Session, confidence: float = 1.0) -> bool:
        if self.HARD_ESCALATE.search(message):
            return True

        if re.search(r"\b(human|engineer|person|speak to|talk to)\b", message, re.IGNORECASE):
            return True

        if self.AGENT_UNSURE.search(response):
            return True

        threshold = float(os.environ.get("ESCALATION_CONFIDENCE_THRESHOLD", "0.4"))
        if confidence < threshold:
            return True

        max_turns = int(os.environ.get("MAX_TURNS_BEFORE_ESCALATE", "6"))
        if len(session.history) > max_turns * 2:
            return True

        return False
