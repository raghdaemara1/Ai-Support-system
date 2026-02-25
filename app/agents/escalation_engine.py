"""
Escalation Engine.
Rules-first (fast, deterministic) escalation detection.
Checks user message, agent response, and conversation turn count.
"""
import re
import os
from typing import List

from app.core.logging import get_logger

logger = get_logger(__name__)


class EscalationEngine:

    SAFETY_PATTERN = re.compile(
        r'\b(fire|smoke|injury|emergency|explosion|danger|critical|'
        r'production stop|urgent|unsafe|shutdown|accident)\b',
        re.IGNORECASE,
    )
    HUMAN_REQUEST_PATTERN = re.compile(
        r'\b(human|support engineer|customer service|person|agent|speak to|talk to|transfer|escalate)\b',
        re.IGNORECASE,
    )
    UNSURE_PATTERN = re.compile(
        r"(don'?t know|cannot find|not sure|no information|"
        r"unclear|no record|consult|not in (my|the) (knowledge|database|kb))",
        re.IGNORECASE,
    )

    def should_escalate(
        self,
        user_message: str,
        agent_response: str,
        history: List = None,
    ) -> bool:
        """
        Determine if the conversation needs immediate human escalation.
        Priority order: safety → human request → agent unsure → turn limit.
        """
        history = history or []
        max_turns = int(os.environ.get("MAX_TURNS_BEFORE_ESCALATE", 6))

        # Count user turns — history may contain LangChain BaseMessage objects or plain dicts.
        # Explicit parentheses prevent operator-precedence ambiguity.
        turn_count = len([
            msg for msg in history
            if (isinstance(msg, dict) and msg.get("role") == "user")
            or (getattr(msg, "type", None) == "human")
        ])

        # Rule 1: safety keyword in user message — always escalate immediately
        if self.SAFETY_PATTERN.search(user_message):
            logger.info("Escalation: safety keyword detected")
            return True

        # Rule 2: user explicitly asked for a human
        if self.HUMAN_REQUEST_PATTERN.search(user_message):
            logger.info("Escalation: human request detected")
            return True

        # Rule 3: agent admitted it does not know the answer
        if agent_response and self.UNSURE_PATTERN.search(agent_response):
            logger.info("Escalation: agent expressed uncertainty")
            return True

        # Rule 4: conversation has dragged on too long without resolution
        if turn_count > max_turns:
            logger.info(
                "Escalation: turn limit exceeded",
                turn_count=turn_count,
                max_turns=max_turns,
            )
            return True

        return False

    def extract_intent(self, user_message: str) -> str:
        """Classify user intent based on keywords."""
        msg = user_message.lower()
        if any(w in msg for w in ["alarm", "fault", "error", "code"]):
            return "fault_lookup"
        if any(w in msg for w in ["ticket", "report", "log"]):
            return "ticket_create"
        if any(w in msg for w in ["escalate", "engineer", "human", "person"]):
            return "escalate"
        return "general"

    def extract_alarm_code(self, user_message: str) -> str | None:
        """Extract a potential alarm / fault code from the message."""
        match = re.search(r'\b(\d{3,5})\b', user_message)
        return match.group(1) if match else None
