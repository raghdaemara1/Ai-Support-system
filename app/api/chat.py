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
from app.models.schemas import ChatRequest, ChatResponse, TenantConfig
from app.services.session_service import SessionService
from app.services.tenant_service import TenantService

router = APIRouter()
logger = get_logger(__name__)


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

    Connect: ws://localhost:8000/chat/ws/{tenant_id}/{customer_id}?token=xxx

    Send: {"message": "Hello"}
    Receive: {"type": "token", "content": "..."} or {"type": "done"}
    """
    await websocket.accept()

    # Verify token if provided (optional for demo)
    if token:
        try:
            verify_token(token, tenant_id)
        except Exception as e:
            await websocket.send_json({"type": "error", "content": str(e)})
            await websocket.close()
            return

    session_service = SessionService(db)
    tenant_service = TenantService(db)

    # Get or create session
    session = await session_service.get_or_create_session(
        tenant_id=tenant_id,
        customer_id=customer_id,
        channel="chat",
    )

    # Get tenant config
    tenant_config = await tenant_service.get_config(tenant_id)

    # Create agent
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
            # Receive message
            data = await websocket.receive_json()
            user_message = data.get("message", "")

            if not user_message:
                continue

            # Save user message
            await session_service.add_message(session.id, "user", user_message)

            # Get conversation history
            history = await session_service.get_history(session.id)

            # Track timing
            start_time = time.time()

            try:
                # Get agent response
                result = await agent.invoke(
                    user_input=user_message,
                    history=history,
                )

                response_text = result.get("output", "")
                latency_ms = int((time.time() - start_time) * 1000)

                # Send response
                await websocket.send_json({
                    "type": "message",
                    "content": response_text,
                    "session_id": session.id,
                })

                # Save assistant message
                await session_service.add_message(
                    session.id,
                    "assistant",
                    response_text,
                    latency_ms=latency_ms,
                )

                await websocket.send_json({"type": "done"})

            except Exception as e:
                logger.error("Agent error", error=str(e), session_id=session.id)
                await websocket.send_json({
                    "type": "error",
                    "content": "I apologize, but I encountered an error. Please try again.",
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
    HTTP endpoint for sending a chat message.

    For simpler integrations that don't need WebSocket.
    """
    session_service = SessionService(db)
    tenant_service = TenantService(db)

    # Get or create session
    session = await session_service.get_or_create_session(
        tenant_id=request.tenant_id,
        customer_id=request.customer_id,
        channel="chat",
        session_id=request.session_id,
    )

    # Get tenant config
    tenant_config = await tenant_service.get_config(request.tenant_id)

    # Create agent
    agent = get_agent_for_channel(
        channel="chat",
        tenant_config=tenant_config,
        tenant_id=request.tenant_id,
    )

    # Save user message
    await session_service.add_message(session.id, "user", request.message)

    # Get conversation history
    history = await session_service.get_history(session.id)

    # Track timing
    start_time = time.time()

    try:
        # Get agent response
        result = await agent.invoke(
            user_input=request.message,
            history=history,
        )

        response_text = result.get("output", "")
        latency_ms = int((time.time() - start_time) * 1000)

        # Save assistant message
        await session_service.add_message(
            session.id,
            "assistant",
            response_text,
            latency_ms=latency_ms,
        )

        # Check if escalated
        escalated = "escalat" in response_text.lower() and "reference number" in response_text.lower()

        return ChatResponse(
            session_id=session.id,
            message=response_text,
            escalated=escalated,
            sources=[],
        )

    except Exception as e:
        logger.error("Agent error", error=str(e))
        raise HTTPException(status_code=500, detail="Agent error occurred")
