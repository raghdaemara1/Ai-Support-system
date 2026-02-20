"""Escalation engine for detecting when to hand off to humans."""
from dataclasses import dataclass
from typing import Optional

from app.core.logging import get_logger
from app.models.schemas import TenantConfig

logger = get_logger(__name__)


DEFAULT_ESCALATION_KEYWORDS = [
    "speak to a human",
    "speak to an agent",
    "talk to a person",
    "real person",
    "human agent",
    "manager",
    "supervisor",
    "refund",
    "cancel my account",
    "lawsuit",
    "lawyer",
    "attorney",
    "terrible",
    "unacceptable",
    "disgusting",
    "fraud",
    "scam",
    "sue you",
    "report you",
    "bbb",
    "better business bureau",
]


@dataclass
class EscalationResult:
    """Result of escalation evaluation."""
    should_escalate: bool
    reason: Optional[str] = None
    urgency: str = "normal"


class EscalationEngine:
    """
    Engine for evaluating whether a conversation should be escalated.

    Checks multiple signals:
    - Keyword matching (explicit requests for humans)
    - Sentiment analysis (angry/frustrated customers)
    - Turn count (conversations going too long)
    """

    def __init__(self, tenant_config: Optional[TenantConfig] = None):
        self.config = tenant_config or TenantConfig()
        self.keywords = (
            self.config.escalation_keywords
            if self.config.escalation_keywords
            else DEFAULT_ESCALATION_KEYWORDS
        )

    async def evaluate(
        self,
        message: str,
        sentiment_score: float = 0.0,
        turn_count: int = 0,
    ) -> EscalationResult:
        """
        Evaluate whether to escalate based on the current message and context.

        Args:
            message: The user's message
            sentiment_score: Current sentiment (-1.0 to 1.0)
            turn_count: Number of conversation turns

        Returns:
            EscalationResult with decision and reason
        """
        message_lower = message.lower()

        # Rule 1: Keyword match
        for keyword in self.keywords:
            if keyword in message_lower:
                logger.info(
                    "Escalation triggered by keyword",
                    keyword=keyword,
                )
                return EscalationResult(
                    should_escalate=True,
                    reason=f"keyword_match:{keyword}",
                    urgency="high" if keyword in ["lawsuit", "lawyer", "attorney", "sue"] else "normal",
                )

        # Rule 2: Sentiment threshold
        if sentiment_score < self.config.sentiment_threshold:
            logger.info(
                "Escalation triggered by negative sentiment",
                sentiment=sentiment_score,
                threshold=self.config.sentiment_threshold,
            )
            return EscalationResult(
                should_escalate=True,
                reason="negative_sentiment",
                urgency="normal",
            )

        # Rule 3: Too many turns
        if turn_count >= self.config.max_turns_before_escalate:
            logger.info(
                "Escalation triggered by turn count",
                turn_count=turn_count,
                max_turns=self.config.max_turns_before_escalate,
            )
            return EscalationResult(
                should_escalate=True,
                reason="max_turns_exceeded",
                urgency="low",
            )

        return EscalationResult(should_escalate=False)

    def analyze_sentiment(self, text: str) -> float:
        """
        Simple sentiment analysis.

        Returns a score from -1.0 (very negative) to 1.0 (very positive).
        This is a basic implementation - could be replaced with a proper
        sentiment analysis model.
        """
        negative_words = {
            "angry": -0.5,
            "frustrated": -0.4,
            "annoyed": -0.3,
            "disappointed": -0.3,
            "terrible": -0.6,
            "horrible": -0.6,
            "awful": -0.5,
            "worst": -0.6,
            "hate": -0.5,
            "useless": -0.4,
            "stupid": -0.4,
            "ridiculous": -0.4,
            "unacceptable": -0.5,
            "never": -0.2,
            "problem": -0.2,
            "issue": -0.1,
            "broken": -0.3,
            "failed": -0.3,
            "wrong": -0.2,
        }

        positive_words = {
            "thank": 0.3,
            "thanks": 0.3,
            "great": 0.4,
            "good": 0.3,
            "excellent": 0.5,
            "perfect": 0.5,
            "helpful": 0.4,
            "appreciate": 0.4,
            "wonderful": 0.5,
            "amazing": 0.5,
            "love": 0.4,
            "happy": 0.4,
            "pleased": 0.3,
        }

        text_lower = text.lower()
        score = 0.0
        word_count = 0

        for word, sentiment in negative_words.items():
            if word in text_lower:
                score += sentiment
                word_count += 1

        for word, sentiment in positive_words.items():
            if word in text_lower:
                score += sentiment
                word_count += 1

        if word_count == 0:
            return 0.0

        # Normalize to -1 to 1 range
        return max(-1.0, min(1.0, score / word_count))
