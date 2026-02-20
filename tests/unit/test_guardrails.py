"""Tests for guardrails module."""
import pytest

from app.core.guardrails import (
    redact_pii,
    detect_pii,
    check_topic_guardrail,
    sanitize_for_logging,
)


class TestPIIDetection:
    """Tests for PII detection and redaction."""

    def test_redact_credit_card(self):
        """Test credit card redaction."""
        text = "My card number is 4111-1111-1111-1111"
        result = redact_pii(text)
        assert "4111" not in result
        assert "[CREDIT_CARD_REDACTED]" in result

    def test_redact_ssn(self):
        """Test SSN redaction."""
        text = "My SSN is 123-45-6789"
        result = redact_pii(text)
        assert "123-45-6789" not in result
        assert "[SSN_REDACTED]" in result

    def test_redact_email(self):
        """Test email redaction."""
        text = "Contact me at john@example.com"
        result = redact_pii(text)
        assert "john@example.com" not in result
        assert "[EMAIL_REDACTED]" in result

    def test_redact_phone(self):
        """Test phone number redaction."""
        text = "Call me at 555-123-4567"
        result = redact_pii(text)
        assert "555-123-4567" not in result
        assert "[PHONE_REDACTED]" in result

    def test_detect_pii_types(self):
        """Test detecting multiple PII types."""
        text = "Email: test@test.com, Phone: 555-123-4567"
        pii_types = detect_pii(text)
        assert "email" in pii_types
        assert "phone" in pii_types

    def test_no_pii(self):
        """Test text without PII."""
        text = "What are your business hours?"
        pii_types = detect_pii(text)
        assert len(pii_types) == 0


class TestTopicGuardrails:
    """Tests for topic filtering."""

    def test_forbidden_topic_blocked(self):
        """Test that forbidden topics are blocked."""
        result = check_topic_guardrail("What is your competitor pricing?")
        assert result.blocked is True
        assert "forbidden_topic" in result.reason

    def test_normal_topic_allowed(self):
        """Test that normal topics are allowed."""
        result = check_topic_guardrail("What are your product features?")
        assert result.blocked is False

    def test_custom_forbidden_topics(self):
        """Test custom forbidden topics."""
        result = check_topic_guardrail(
            "Tell me about the secret project",
            forbidden=["secret project", "classified"],
        )
        assert result.blocked is True


class TestSanitizeForLogging:
    """Tests for log sanitization."""

    def test_truncates_long_text(self):
        """Test that long text is truncated."""
        long_text = "x" * 1000
        result = sanitize_for_logging(long_text, max_length=100)
        assert len(result) <= 103  # 100 + "..."

    def test_redacts_pii_in_logs(self):
        """Test that PII is redacted in logs."""
        text = "Customer email: test@example.com"
        result = sanitize_for_logging(text)
        assert "test@example.com" not in result
