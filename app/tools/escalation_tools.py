"""Escalation tools for human handoff."""
from typing import Literal

from langchain.tools import tool

from app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory escalation queue (would be a database/queue in production)
_escalation_queue: list[dict] = []


@tool
async def escalate_to_human(
    session_id: str,
    reason: str,
    urgency: str = "normal",
) -> str:
    """
    Transfer this conversation to a human support agent.

    ALWAYS use this tool when:
    - The customer explicitly requests to speak with a human
    - The customer is frustrated, angry, or upset
    - The issue involves billing disputes, legal matters, or formal complaints
    - You've tried multiple approaches but cannot resolve the issue
    - The question requires access to systems or information you don't have

    Args:
        session_id: The current conversation session ID
        reason: Brief description of why the conversation is being escalated
        urgency: Priority level - "low", "normal", or "high"

    Returns:
        A message to relay to the customer about the escalation.
    """
    try:
        # Generate a ticket ID
        import uuid
        ticket_id = str(uuid.uuid4())[:8].upper()

        # Calculate estimated wait time based on urgency
        wait_times = {
            "low": "within 24 hours",
            "normal": "within 2 hours",
            "high": "within 15 minutes",
        }
        wait_time = wait_times.get(urgency, "within 2 hours")

        # Add to escalation queue (in-memory for demo)
        escalation = {
            "ticket_id": ticket_id,
            "session_id": session_id,
            "reason": reason,
            "urgency": urgency,
            "status": "pending",
        }
        _escalation_queue.append(escalation)

        logger.info(
            "Escalation triggered",
            ticket_id=ticket_id,
            session_id=session_id,
            reason=reason,
            urgency=urgency,
        )

        return (
            f"I'm connecting you with a human support specialist now. "
            f"Your reference number is #{ticket_id}. "
            f"A support agent will reach out {wait_time}. "
            f"Is there anything else I can help you with while you wait?"
        )

    except Exception as e:
        logger.error("Escalation failed", session_id=session_id, error=str(e))
        return (
            "I apologize, but I'm having trouble connecting you with a human agent. "
            "Please try calling our support line directly or email support@company.com."
        )


def get_pending_escalations() -> list[dict]:
    """Get all pending escalations (for admin/dashboard use)."""
    return [e for e in _escalation_queue if e["status"] == "pending"]


def resolve_escalation(ticket_id: str) -> bool:
    """Mark an escalation as resolved."""
    for escalation in _escalation_queue:
        if escalation["ticket_id"] == ticket_id:
            escalation["status"] = "resolved"
            return True
    return False
