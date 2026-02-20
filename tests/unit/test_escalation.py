"""Tests for escalation engine."""
import pytest

from app.escalation.engine import EscalationEngine, EscalationResult
from app.models.schemas import TenantConfig


@pytest.fixture
def engine():
    """Create escalation engine with default config."""
    return EscalationEngine()


@pytest.fixture
def custom_engine():
    """Create escalation engine with custom config."""
    config = TenantConfig(
        escalation_keywords=["urgent", "emergency"],
        sentiment_threshold=-0.5,
        max_turns_before_escalate=5,
    )
    return EscalationEngine(tenant_config=config)


class TestEscalationEngine:
    """Tests for EscalationEngine."""

    @pytest.mark.asyncio
    async def test_keyword_escalation(self, engine):
        """Test escalation triggered by keyword."""
        result = await engine.evaluate("I want to speak to a human")
        assert result.should_escalate is True
        assert "keyword" in result.reason

    @pytest.mark.asyncio
    async def test_manager_keyword(self, engine):
        """Test escalation for manager keyword."""
        result = await engine.evaluate("Get me your manager now!")
        assert result.should_escalate is True

    @pytest.mark.asyncio
    async def test_legal_keyword_high_urgency(self, engine):
        """Test that legal keywords trigger high urgency."""
        result = await engine.evaluate("I'm going to sue you")
        assert result.should_escalate is True
        assert result.urgency == "high"

    @pytest.mark.asyncio
    async def test_no_escalation_normal_message(self, engine):
        """Test no escalation for normal message."""
        result = await engine.evaluate("What are your store hours?")
        assert result.should_escalate is False

    @pytest.mark.asyncio
    async def test_sentiment_escalation(self, engine):
        """Test escalation triggered by sentiment."""
        result = await engine.evaluate(
            "This is okay",
            sentiment_score=-0.8,
        )
        assert result.should_escalate is True
        assert result.reason == "negative_sentiment"

    @pytest.mark.asyncio
    async def test_turn_count_escalation(self, engine):
        """Test escalation triggered by turn count."""
        result = await engine.evaluate(
            "Hello",
            turn_count=15,
        )
        assert result.should_escalate is True
        assert result.reason == "max_turns_exceeded"

    @pytest.mark.asyncio
    async def test_custom_keywords(self, custom_engine):
        """Test custom escalation keywords."""
        result = await custom_engine.evaluate("This is an emergency!")
        assert result.should_escalate is True

    def test_sentiment_analysis_negative(self, engine):
        """Test sentiment analysis with negative words."""
        score = engine.analyze_sentiment("This is terrible and I'm very angry!")
        assert score < 0

    def test_sentiment_analysis_positive(self, engine):
        """Test sentiment analysis with positive words."""
        score = engine.analyze_sentiment("Thank you, this is great!")
        assert score > 0

    def test_sentiment_analysis_neutral(self, engine):
        """Test sentiment analysis with neutral message."""
        score = engine.analyze_sentiment("What time does the store open?")
        assert score == 0.0
