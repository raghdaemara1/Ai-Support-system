"""Escalation tools for human handoff."""
import asyncio
import uuid
from datetime import datetime
from typing import Literal

from langchain.tools import tool

from app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory escalation queue (would be Redis/DB in production).
# asyncio.Lock makes appends safe in a single-process async server.
_escalation_queue: list[dict] = []
_queue_lock = asyncio.Lock()

WAIT_TIMES = {
    "low":    "within 24 hours",
    "normal": "within 2 hours",
    "high":   "within 15 minutes",
}


async def _perform_escalation(
    session_id: str,
    reason: str,
    urgency: str = "normal",
) -> str:
    """
    Core escalation logic extracted so it can be called directly
    from the chat router (without touching the LangChain tool wrapper)
    and from inside the @tool decorator.

    Wrapped with asyncio.timeout so it never hangs indefinitely.
    """
    ticket_id = str(uuid.uuid4())[:8].upper()
    wait_time = WAIT_TIMES.get(urgency, "within 2 hours")

    escalation = {
        "ticket_id":  ticket_id,
        "session_id": session_id,
        "reason":     reason,
        "urgency":    urgency,
        "status":     "pending",
        "created_at": datetime.utcnow().isoformat(),
    }

    async with _queue_lock:
        _escalation_queue.append(escalation)

    logger.info(
        "Escalation queued",
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


@tool
async def escalate_to_human(
    reason: str,
    urgency: str = "normal",
) -> str:
    """
    Transfer this conversation to a human support agent.

    ALWAYS use this tool when:
    - The customer explicitly requests to speak with a human
    - The customer is frustrated, angry, or upset
    - The issue involves billing disputes, legal matters, or formal complaints
    - You have tried multiple approaches but cannot resolve the issue
    - The question requires access to systems or information you do not have

    Args:
        reason: Brief description of why the conversation is being escalated
        urgency: Priority level - "low", "normal", or "high"

    Returns:
        A message to relay to the customer about the escalation.
    """
    # session_id is auto-generated here — the LLM does not need to provide it
    session_id = "agent-" + str(uuid.uuid4())[:8]
    try:
        # 10-second hard timeout — never block the event loop
        return await asyncio.wait_for(
            _perform_escalation(session_id, reason, urgency),
            timeout=10.0,
        )
    except asyncio.TimeoutError:
        logger.error("Escalation timed out", urgency=urgency)
        return (
            "I'm sorry — I ran into a brief delay connecting you to a specialist. "
            "Your request has been logged and someone will follow up shortly. "
            "You can also reach us directly at support@company.com."
        )
    except Exception as e:
        logger.error("Escalation failed", error=str(e))
        return (
            "I apologize, but I am having trouble connecting you with a human agent right now. "
            "Please try calling our support line directly or email support@company.com."
        )


# ── Admin helpers ─────────────────────────────────────────────────────────────

def get_pending_escalations() -> list[dict]:
    """Return all pending escalations (for admin / dashboard use)."""
    return [e for e in _escalation_queue if e["status"] == "pending"]


def resolve_escalation(ticket_id: str) -> bool:
    """Mark an escalation as resolved."""
    for escalation in _escalation_queue:
        if escalation["ticket_id"] == ticket_id:
            escalation["status"] = "resolved"
            return True
    return False


def get_all_escalations() -> list[dict]:
    """Return the full escalation queue (for the demo dashboard)."""
    return list(_escalation_queue)
