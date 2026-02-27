"""
Escalation Engine.
Rules-first (fast, deterministic) escalation detection.
Checks user message, agent response, and conversation turn count.
"""
import re
import os
from dataclasses import dataclass
from typing import List, Optional


@dataclass
class EscalationResult:
    """Detailed result of an escalation check."""
    should_escalate: bool
    reason: Optional[str] = None
    urgency: str = "low"  # low, medium, high


class EscalationEngine:

    def __init__(self, tenant_config=None):
        self.tenant_config = tenant_config

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
    NEGATIVE_WORDS = {
        "terrible", "angry", "bad", "horrible", "awful", "sue", "manager", "complaint"
    }
    POSITIVE_WORDS = {
        "thank", "great", "good", "happy", "excellent", "awesome"
    }

    def analyze_sentiment(self, text: str) -> float:
        """Simple keyword-based sentiment analysis."""
        words = set(re.findall(r'\w+', text.lower()))
        pos = len(words.intersection(self.POSITIVE_WORDS))
        neg = len(words.intersection(self.NEGATIVE_WORDS))
        
        if pos == 0 and neg == 0:
            return 0.0
        return (pos - neg) / (pos + neg)

    async def evaluate(
        self,
        user_message: str,
        agent_response: str = "",
        history: List = None,
        sentiment_score: Optional[float] = None,
        turn_count: Optional[int] = None,
    ) -> EscalationResult:
        """
        Evaluate if a message or conversation state warrants escalation.
        Uses tenant_config for custom keywords, sentiment threshold, and max turns
        when provided — falling back to safe defaults otherwise.
        """
        history = history or []

        # Resolve thresholds from tenant config (if set) or env/defaults
        if self.tenant_config:
            max_turns = self.tenant_config.max_turns_before_escalate
            sentiment_threshold = self.tenant_config.sentiment_threshold
            custom_keywords = [kw.lower() for kw in self.tenant_config.escalation_keywords]
        else:
            max_turns = int(os.environ.get("MAX_TURNS_BEFORE_ESCALATE", 6))
            sentiment_threshold = -0.5
            custom_keywords = []

        # 1. Tenant custom escalation keywords (highest priority after safety)
        if custom_keywords:
            msg_lower = user_message.lower()
            if any(kw in msg_lower for kw in custom_keywords):
                return EscalationResult(True, "keyword", "medium")

        # 2. Check for high-urgency legal/threat keywords
        if "sue" in user_message.lower() or "manager" in user_message.lower():
            return EscalationResult(True, "keyword", "high")

        # 3. Check general safety patterns
        if self.SAFETY_PATTERN.search(user_message):
            return EscalationResult(True, "keyword", "medium")

        # 4. Check for human requests
        if self.HUMAN_REQUEST_PATTERN.search(user_message):
            return EscalationResult(True, "keyword", "low")

        # 5. Agent uncertainty
        if agent_response and self.UNSURE_PATTERN.search(agent_response):
            return EscalationResult(True, "agent_uncertainty", "low")

        # 6. Sentiment analysis (if provided or calculated)
        score = sentiment_score if sentiment_score is not None else self.analyze_sentiment(user_message)
        if score < sentiment_threshold:
            return EscalationResult(True, "negative_sentiment", "medium")

        # 7. Turn count
        current_turns = turn_count if turn_count is not None else len([
            msg for msg in history
            if (isinstance(msg, dict) and msg.get("role") == "user")
            or (getattr(msg, "type", None) == "human")
        ])
        if current_turns > max_turns:
            return EscalationResult(True, "max_turns_exceeded", "low")

        return EscalationResult(False)

    def should_escalate(
        self,
        user_message: str,
        agent_response: str,
        history: List = None,
    ) -> bool:
        """
        .. deprecated::
            Use ``await evaluate()`` for full escalation logic including
            sentiment analysis, turn count, and urgency classification.
            This method only checks the three core regex rules.
        """
        if self.SAFETY_PATTERN.search(user_message) or \
           self.HUMAN_REQUEST_PATTERN.search(user_message) or \
           (agent_response and self.UNSURE_PATTERN.search(agent_response)):
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
