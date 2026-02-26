"""
n8n → Agent callback endpoints.

n8n workflows call these endpoints to push results back into the agent platform:

  POST /n8n/ticket-resolved      — human agent resolved a ticket via n8n workflow
  POST /n8n/ingest-trigger        — n8n triggers knowledge base re-ingestion
  GET  /n8n/escalations          — n8n polls pending escalations for its dashboards
  GET  /n8n/status               — health check for the n8n ↔ agent connection
"""
from datetime import datetime

from fastapi import APIRouter, Body, HTTPException
from pydantic import BaseModel

from app.core.logging import get_logger
from app.tools.escalation_tools import (
    get_all_escalations,
    get_pending_escalations,
    resolve_escalation,
)

logger = get_logger(__name__)

router = APIRouter(prefix="/n8n", tags=["n8n"])


# ── Pydantic models for n8n payloads ──────────────────────────────────────────

class TicketResolvedPayload(BaseModel):
    ticket_id: str
    resolved_by: str = "n8n-workflow"
    resolution_note: str = ""


class IngestTriggerPayload(BaseModel):
    tenant_id: str
    source_url: str = ""
    source_type: str = "url"       # "url" | "pdf" | "zendesk"
    triggered_by: str = "n8n"


# ── Endpoints ─────────────────────────────────────────────────────────────────

@router.get("/status")
async def n8n_status():
    """
    Health-check endpoint for n8n to verify the agent is reachable.
    Add this as an HTTP Request node in your n8n workflow to confirm connectivity.
    """
    pending = get_pending_escalations()
    return {
        "status":            "connected",
        "agent":             "AI Customer Support Agent",
        "pending_escalations": len(pending),
        "timestamp":         datetime.utcnow().isoformat(),
    }


@router.get("/escalations")
async def list_escalations(pending_only: bool = True):
    """
    Return escalation queue for n8n polling workflows.

    n8n use case: Schedule trigger (every 5 min) → GET /n8n/escalations
    → IF has_pending → notify Slack channel → mark as handled externally.
    """
    escalations = get_pending_escalations() if pending_only else get_all_escalations()
    return {
        "count":       len(escalations),
        "escalations": escalations,
    }


@router.post("/ticket-resolved")
async def ticket_resolved(payload: TicketResolvedPayload):
    """
    Called by n8n when a human agent marks a ticket as resolved
    (e.g., after a Zendesk status-change webhook triggers an n8n workflow).

    n8n workflow: Zendesk webhook → filter resolved → POST /n8n/ticket-resolved
    """
    success = resolve_escalation(payload.ticket_id)
    if not success:
        raise HTTPException(
            status_code=404,
            detail=f"Ticket #{payload.ticket_id} not found or already resolved.",
        )

    logger.info(
        "Ticket resolved via n8n",
        ticket_id=payload.ticket_id,
        resolved_by=payload.resolved_by,
        note=payload.resolution_note,
    )
    return {
        "status":    "resolved",
        "ticket_id": payload.ticket_id,
        "resolved_by": payload.resolved_by,
    }


@router.post("/ingest-trigger")
async def ingest_trigger(payload: IngestTriggerPayload):
    """
    n8n triggers a knowledge base re-ingestion for a tenant.

    n8n use case:
      Watch Google Drive folder → new PDF uploaded
      → POST /n8n/ingest-trigger {tenant_id, source_url, source_type}
      → agent ingests the document into ChromaDB

    The actual ingestion runs in the background so n8n gets an immediate 202.
    """
    import asyncio
    from app.knowledge_base.builder import ingest_from_url

    logger.info(
        "Ingest triggered by n8n",
        tenant_id=payload.tenant_id,
        source=payload.source_url,
        type=payload.source_type,
    )

    # Run ingestion in background — n8n doesn't need to wait for it
    asyncio.create_task(
        ingest_from_url(
            tenant_id=payload.tenant_id,
            url=payload.source_url,
        )
    )

    return {
        "status":    "accepted",
        "message":   f"Ingestion queued for tenant {payload.tenant_id}",
        "source":    payload.source_url,
    }
