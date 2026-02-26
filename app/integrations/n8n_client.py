"""
n8n Workflow Automation Client.

Sends webhook events from the AI agent to n8n for downstream automation:
  - Escalation alerts → Slack / email / Zendesk
  - New session events → CRM lead creation
  - Knowledge base updates → n8n-triggered re-ingestion

n8n also calls back into the agent via POST /n8n/... endpoints
(see app/api/n8n_webhooks.py).
"""
import asyncio
from typing import Any

import httpx

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Shared async HTTP client — created once, reused across all calls.
# httpx.AsyncClient is connection-pool-aware and safe for concurrent use.
_http_client: httpx.AsyncClient | None = None


def _get_client() -> httpx.AsyncClient:
    global _http_client
    if _http_client is None or _http_client.is_closed:
        _http_client = httpx.AsyncClient(
            base_url=settings.n8n_base_url,
            timeout=httpx.Timeout(10.0),
            headers={
                "Content-Type": "application/json",
                # Include n8n API key if set (used by n8n Cloud or protected instances)
                **({"X-N8N-API-KEY": settings.n8n_api_key} if settings.n8n_api_key else {}),
            },
        )
    return _http_client


async def _post_webhook(path: str, payload: dict[str, Any]) -> bool:
    """
    Fire-and-forget POST to an n8n webhook URL.
    Returns True on success, False on any error.
    Never raises — n8n is optional infrastructure.
    """
    if not settings.n8n_enabled:
        logger.debug("n8n disabled — skipping webhook", path=path)
        return False

    try:
        client = _get_client()
        response = await asyncio.wait_for(
            client.post(path, json=payload),
            timeout=8.0,
        )
        response.raise_for_status()
        logger.info(
            "n8n webhook sent",
            path=path,
            status=response.status_code,
        )
        return True

    except asyncio.TimeoutError:
        logger.warning("n8n webhook timed out", path=path)
        return False
    except httpx.ConnectError:
        logger.warning("n8n not reachable — is it running?", url=settings.n8n_base_url + path)
        return False
    except httpx.HTTPStatusError as exc:
        logger.warning("n8n webhook HTTP error", path=path, status=exc.response.status_code)
        return False
    except Exception as exc:
        logger.warning("n8n webhook unexpected error", path=path, error=str(exc))
        return False


# ── Public API ─────────────────────────────────────────────────────────────────

async def notify_escalation(
    ticket_id: str,
    session_id: str,
    reason: str,
    urgency: str,
    customer_message: str = "",
    tenant_id: str = "",
) -> bool:
    """
    Notify n8n when a customer conversation is escalated to a human agent.

    Example n8n workflow triggered:
      Webhook → Slack #support-escalations → Create Zendesk ticket → Send customer email
    """
    payload = {
        "event":            "escalation",
        "ticket_id":        ticket_id,
        "session_id":       session_id,
        "reason":           reason,
        "urgency":          urgency,
        "customer_message": customer_message,
        "tenant_id":        tenant_id,
        "agent_source":     "ai-support-agent",
    }
    return await _post_webhook(settings.n8n_webhook_escalation, payload)


async def notify_new_session(
    session_id: str,
    tenant_id: str,
    channel: str,
    customer_id: str = "",
) -> bool:
    """
    Notify n8n when a new support session starts.

    Example n8n workflow: new chat → log to Google Sheets → tag in CRM
    """
    payload = {
        "event":       "new_session",
        "session_id":  session_id,
        "tenant_id":   tenant_id,
        "channel":     channel,
        "customer_id": customer_id,
    }
    return await _post_webhook(settings.n8n_webhook_new_session, payload)


async def close() -> None:
    """Close the shared HTTP client. Call on app shutdown."""
    global _http_client
    if _http_client and not _http_client.is_closed:
        await _http_client.aclose()
        _http_client = None
