"""Chat WebSocket and HTTP endpoints."""
import asyncio
import time
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from app.agents.support_agent import get_agent_for_channel
from app.core.logging import get_logger
from app.core.security import verify_token
from app.dependencies import get_db_session
from app.models.schemas import ChatRequest, ChatResponse, TenantConfig, EmailRequest
from app.services.session_service import SessionService
from app.services.tenant_service import TenantService
from app.channels.email_handler import _send_reply
from app.agents.escalation_engine import EscalationEngine
# Import the bare async function — NOT the @tool wrapper — so we can call it
# directly from the router without going through the LangChain tool executor.
from app.tools.escalation_tools import _perform_escalation

router = APIRouter()
logger = get_logger(__name__)

# Single shared escalation engine (stateless — safe to share)
escalation_engine = EscalationEngine()

# Hard timeout for a single LLM round-trip (seconds)
LLM_TIMEOUT = 45


@router.websocket("/ws/{tenant_id}/{customer_id}")
async def chat_websocket(
    websocket: WebSocket,
    tenant_id: str,
    customer_id: str,
    token: Optional[str] = Query(None),
    db: AsyncSession = Depends(get_db_session),
):
    """
    WebSocket endpoint for real-time chat.

    Connect : ws://localhost:8001/chat/ws/{tenant_id}/{customer_id}?token=xxx
    Send    : {"message": "Hello"}
    Receive : {"type": "message", "content": "...", "session_id": "..."}
              {"type": "done", "escalated": false, "intent": "general", "latency_ms": 340}
              {"type": "error", "content": "..."}
    """
    await websocket.accept()

    if token:
        try:
            verify_token(token, tenant_id)
        except Exception as e:
            await websocket.send_json({"type": "error", "content": str(e)})
            await websocket.close()
            return

    session_service = SessionService(db)
    tenant_service  = TenantService(db)

    session = await session_service.get_or_create_session(
        tenant_id=tenant_id,
        customer_id=customer_id,
        channel="chat",
    )
    tenant_config = await tenant_service.get_config(tenant_id)
    agent = get_agent_for_channel(
        channel="chat",
        tenant_config=tenant_config,
        tenant_id=tenant_id,
    )

    logger.info(
        "WebSocket connected",
        session_id=session.id,
        tenant_id=tenant_id,
        customer_id=customer_id,
    )

    try:
        while True:
            data = await websocket.receive_json()
            user_message = data.get("message", "").strip()
            if not user_message:
                continue

            await session_service.add_message(session.id, "user", user_message)
            history    = await session_service.get_history(session.id)
            start_time = time.time()

            print(f"\n[DEBUG-FLOW] [WS] Received message: '{user_message}' from session: {session.id}")
            print(f"[DEBUG-FLOW] [WS] Retrieved history. Number of past messages: {len(history)}")
            print(f"[DEBUG-FLOW] [WS] Invoking Agent (LLM + Tools)...")

            try:
                # ── LLM call with hard timeout ──────────────────────────────
                result = await asyncio.wait_for(
                    agent.invoke(user_input=user_message, history=history),
                    timeout=LLM_TIMEOUT,
                )
                print(f"[DEBUG-FLOW] [WS] Agent response received in {time.time() - start_time:.2f}s")

                response_text = result.get("output", "")
                latency_ms    = int((time.time() - start_time) * 1000)

                # ── Escalation check (before we tell the client we're done) ─
                print(f"[DEBUG-FLOW] [WS] Checking for system escalation. Latency so far: {latency_ms}ms")
                is_escalated = escalation_engine.should_escalate(
                    user_message=user_message,
                    agent_response=response_text,
                    history=history,
                )
                intent = escalation_engine.extract_intent(user_message)

                if is_escalated:
                    urgency = (
                        "high"
                        if escalation_engine.SAFETY_PATTERN.search(user_message)
                        else "normal"
                    )
                    logger.info(
                        "Escalation triggered (WebSocket)",
                        session_id=session.id,
                        urgency=urgency,
                    )
                    try:
                        # Call the bare async function — not the @tool wrapper
                        await asyncio.wait_for(
                            _perform_escalation(
                                session_id=session.id,
                                reason="User requested human, safety issue, or agent uncertain",
                                urgency=urgency,
                            ),
                            timeout=10.0,
                        )
                    except asyncio.TimeoutError:
                        logger.warning("Escalation queue write timed out", session_id=session.id)

                # ── Send message then completion frame ──────────────────────
                await websocket.send_json({
                    "type":       "message",
                    "content":    response_text,
                    "session_id": session.id,
                })
                await websocket.send_json({
                    "type":       "done",
                    "escalated":  is_escalated,
                    "intent":     intent,
                    "latency_ms": latency_ms,
                })
                print(f"[DEBUG-FLOW] [WS] Sent response to UI. Escalated: {is_escalated}, Intent: {intent}")

                # ── Persist assistant message ───────────────────────────────
                await session_service.add_message(
                    session.id,
                    "assistant",
                    response_text,
                    latency_ms=latency_ms,
                )

            except asyncio.TimeoutError:
                logger.error(
                    "LLM timeout (WebSocket)",
                    session_id=session.id,
                    timeout=LLM_TIMEOUT,
                )
                await websocket.send_json({
                    "type":    "error",
                    "content": (
                        "Sorry, the response took too long. "
                        "Please try again or ask a simpler question."
                    ),
                })

            except Exception as e:
                logger.error("Agent error (WebSocket)", error=str(e), session_id=session.id)
                await websocket.send_json({
                    "type":    "error",
                    "content": "I encountered an error processing your request. Please try again.",
                })

    except WebSocketDisconnect:
        logger.info("WebSocket disconnected", session_id=session.id)
        await session_service.close_session(session.id)


@router.post("/message", response_model=ChatResponse)
async def send_message(
    request: ChatRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ChatResponse:
    """
    HTTP endpoint for a single chat turn.

    For integrations that do not need a persistent WebSocket connection.
    """
    session_service = SessionService(db)
    tenant_service  = TenantService(db)

    session = await session_service.get_or_create_session(
        tenant_id=request.tenant_id,
        customer_id=request.customer_id,
        channel="chat",
        session_id=request.session_id,
    )
    tenant_config = await tenant_service.get_config(request.tenant_id)
    agent = get_agent_for_channel(
        channel="chat",
        tenant_config=tenant_config,
        tenant_id=request.tenant_id,
    )

    await session_service.add_message(session.id, "user", request.message)
    history    = await session_service.get_history(session.id)
    start_time = time.time()

    print(f"\n[DEBUG-FLOW] [HTTP] Received message: '{request.message}' from session: {session.id}")
    print(f"[DEBUG-FLOW] [HTTP] Retrieved history. Number of past messages: {len(history)}")
    print(f"[DEBUG-FLOW] [HTTP] Invoking Agent...")

    try:
        # ── LLM call with hard timeout ──────────────────────────────────────
        result = await asyncio.wait_for(
            agent.invoke(user_input=request.message, history=history),
            timeout=LLM_TIMEOUT,
        )
        print(f"[DEBUG-FLOW] [HTTP] Agent response received in {time.time() - start_time:.2f}s")

        response_text = result.get("output", "")
        latency_ms    = int((time.time() - start_time) * 1000)

        await session_service.add_message(
            session.id,
            "assistant",
            response_text,
            latency_ms=latency_ms,
        )

        # ── Escalation check ────────────────────────────────────────────────
        print(f"[DEBUG-FLOW] [HTTP] Checking for system escalation...")
        is_escalated = escalation_engine.should_escalate(
            user_message=request.message,
            agent_response=response_text,
            history=history,
        )
        intent = escalation_engine.extract_intent(request.message)

        if is_escalated:
            urgency = (
                "high"
                if escalation_engine.SAFETY_PATTERN.search(request.message)
                else "normal"
            )
            logger.info(
                "Escalation triggered (HTTP)",
                session_id=session.id,
                urgency=urgency,
            )
            try:
                await asyncio.wait_for(
                    _perform_escalation(
                        session_id=session.id,
                        reason="User requested human, safety issue, or agent uncertain",
                        urgency=urgency,
                    ),
                    timeout=10.0,
                )
            except asyncio.TimeoutError:
                logger.warning("Escalation queue write timed out", session_id=session.id)

        print(f"[DEBUG-FLOW] [HTTP] Completed processing. Escalated: {is_escalated}, Intent: {intent}")
        return ChatResponse(
            session_id=session.id,
            message=response_text,
            escalated=is_escalated,
            intent=intent,
            sources=[],
        )

    except asyncio.TimeoutError:
        logger.error(
            "LLM timeout (HTTP)",
            session_id=session.id if hasattr(session, "id") else "unknown",
            timeout=LLM_TIMEOUT,
        )
        raise HTTPException(
            status_code=504,
            detail=(
                "The AI agent took too long to respond. "
                "Please try again — shorter messages tend to respond faster."
            ),
        )

    except Exception as e:
        import re as _re
        error_str = str(e)
        logger.error("Agent error (HTTP)", error=error_str[:300])

        # Rate-limit — surface clearly
        if "rate_limit" in error_str.lower() or "429" in error_str or "ratelimit" in error_str.lower():
            raise HTTPException(
                status_code=429,
                detail="The AI service is temporarily rate-limited. Please wait a few minutes and try again.",
            )

        # Groq tool_use_failed (400): smaller models sometimes mix text + <function=...>
        # Recover the text portion from failed_generation rather than returning a 500.
        if "tool_use_failed" in error_str or "failed_generation" in error_str:
            fg_match = _re.search(r"'failed_generation':\s*'(.*?)'[,}]", error_str, _re.DOTALL)
            if fg_match:
                fg_text = fg_match.group(1).replace("\\'", "'").replace("\\n", "\n")
                # Extract text before any <function=...> call
                clean_text = _re.split(r"\s*<function=", fg_text)[0].strip()
                if clean_text:
                    # Check if the model intended to escalate
                    wants_escalate = "escalate_to_human" in fg_text
                    is_escalated = wants_escalate or escalation_engine.should_escalate(
                        user_message=request.message,
                        agent_response=clean_text,
                        history=[],
                    )
                    if wants_escalate:
                        try:
                            await asyncio.wait_for(
                                _perform_escalation(
                                    session_id=session.id,
                                    reason="Escalated via model intent recovery",
                                    urgency="normal",
                                ),
                                timeout=10.0,
                            )
                        except asyncio.TimeoutError:
                            pass

                    await session_service.add_message(
                        session.id, "assistant", clean_text, latency_ms=0
                    )
                    return ChatResponse(
                        session_id=session.id,
                        message=clean_text,
                        escalated=is_escalated,
                        intent=escalation_engine.extract_intent(request.message),
                        sources=[],
                    )

        raise HTTPException(status_code=500, detail=f"Agent error: {error_str[:200]}")


@router.post("/email/send", response_model=ChatResponse)
async def send_email_endpoint(
    request: EmailRequest,
    db: AsyncSession = Depends(get_db_session),
) -> ChatResponse:
    """
    HTTP endpoint for inbound emails from the UI.
    Uses the agent to draft a reply, checks for escalation, and dispatches via SMTP.
    """
    session_service = SessionService(db)
    tenant_service  = TenantService(db)

    # Use email channel
    session = await session_service.get_or_create_session(
        tenant_id=request.tenant_id,
        customer_id=request.customer_email,
        channel="email",
    )
    tenant_config = await tenant_service.get_config(request.tenant_id)
    agent = get_agent_for_channel(
        channel="email",
        tenant_config=tenant_config,
        tenant_id=request.tenant_id,
    )

    combined_message = f"Subject: {request.subject}\n\n{request.body}"
    await session_service.add_message(session.id, "user", combined_message)
    history = await session_service.get_history(session.id)
    start_time = time.time()

    try:
        # ── LLM call with hard timeout ──
        result = await asyncio.wait_for(
            agent.invoke(user_input=combined_message, history=history),
            timeout=LLM_TIMEOUT + 15, # Emails might take slightly longer
        )

        response_text = result.get("output", "")
        latency_ms    = int((time.time() - start_time) * 1000)

        await session_service.add_message(
            session.id,
            "assistant",
            response_text,
            latency_ms=latency_ms,
        )

        # ── Escalation check ──
        is_escalated = escalation_engine.should_escalate(
            user_message=combined_message,
            agent_response=response_text,
            history=history,
        )
        intent = escalation_engine.extract_intent(combined_message)

        if is_escalated:
            urgency = "high" if escalation_engine.SAFETY_PATTERN.search(combined_message) else "normal"
            logger.info("Escalation triggered (Email)", session_id=session.id, urgency=urgency)
            try:
                await asyncio.wait_for(
                    _perform_escalation(
                        session_id=session.id,
                        reason="Standard email escalation rules",
                        urgency=urgency,
                    ),
                    timeout=10.0,
                )
            except asyncio.TimeoutError:
                pass

        # Dispatch real email via SMTP handler
        try:
            _send_reply(
                to=request.customer_email,
                subject=f"Re: {request.subject}",
                body=response_text
            )
            logger.info("Real SMTP email dispatched", to=request.customer_email)
        except Exception as e:
            logger.error("Failed to send real SMTP email (check .env credentials)", error=str(e))
            # Even if SMTP fails, return the drafted response to the UI
            pass

        return ChatResponse(
            session_id=session.id,
            message=response_text,
            escalated=is_escalated,
            intent=intent,
            sources=[],
        )

    except asyncio.TimeoutError:
        raise HTTPException(status_code=504, detail="The Email agent took too long to respond.")
    except Exception as e:
        logger.error("Email Agent error", error=str(e))
        raise HTTPException(status_code=500, detail=f"Agent error: {str(e)[:200]}")
