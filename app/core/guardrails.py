"""PII detection, topic filtering, and safety guardrails."""
import re
from typing import NamedTuple


class GuardrailResult(NamedTuple):
    """Result of guardrail check."""
    blocked: bool
    reason: str | None = None


PII_PATTERNS = {
    "credit_card": r"\b\d{4}[\s-]?\d{4}[\s-]?\d{4}[\s-]?\d{4}\b",
    "ssn": r"\b\d{3}-\d{2}-\d{4}\b",
    "email": r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Z|a-z]{2,}\b",
    "phone": r"\b[\+]?[(]?[0-9]{3}[)]?[-\s\.]?[0-9]{3}[-\s\.]?[0-9]{4,6}\b",
}


def redact_pii(text: str) -> str:
    """Redact PII from text before logging or storing."""
    for label, pattern in PII_PATTERNS.items():
        text = re.sub(pattern, f"[{label.upper()}_REDACTED]", text)
    return text


def detect_pii(text: str) -> list[str]:
    """Detect PII types present in text."""
    found = []
    for label, pattern in PII_PATTERNS.items():
        if re.search(pattern, text):
            found.append(label)
    return found


FORBIDDEN_TOPICS = [
    "competitor pricing",
    "internal salary",
    "unreleased products",
    "employee personal info",
]


def check_topic_guardrail(message: str, forbidden: list[str] | None = None) -> GuardrailResult:
    """Check if message contains forbidden topics."""
    topics_to_check = forbidden or FORBIDDEN_TOPICS
    message_lower = message.lower()

    for topic in topics_to_check:
        if topic in message_lower:
            return GuardrailResult(blocked=True, reason=f"forbidden_topic:{topic}")

    return GuardrailResult(blocked=False)


def sanitize_for_logging(text: str, max_length: int = 500) -> str:
    """Sanitize text for safe logging."""
    sanitized = redact_pii(text)
    if len(sanitized) > max_length:
        sanitized = sanitized[:max_length] + "..."
    return sanitized
