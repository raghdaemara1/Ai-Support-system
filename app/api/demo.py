from fastapi import APIRouter, WebSocket

from app.agent.support_agent import SupportAgent
from app.channels.chat import chat_websocket_handler
from app.storage.session import SessionManager

router = APIRouter()
_agent: SupportAgent | None = None
_session_manager = SessionManager()


def _get_agent() -> SupportAgent:
    global _agent
    if _agent is None:
        _agent = SupportAgent()
    return _agent


@router.websocket("/ws/chat/{session_id}")
async def websocket_endpoint(websocket: WebSocket, session_id: str):
    await chat_websocket_handler(websocket, session_id)


@router.post("/api/chat")
async def chat_rest(payload: dict):
    session_id = payload.get("session_id", "demo")
    machine = payload.get("machine")
    message = payload.get("message", "")

    session = _session_manager.get_or_create(session_id, channel="chat")
    if machine:
        session.machine = machine

    _session_manager.add_message(session_id, role="user", content=message)
    response = await _get_agent().respond(message=message, session=session)
    _session_manager.add_message(session_id, role="agent", content=response.content)

    return {
        "message": response.content,
        "intent": response.intent,
        "confidence": response.confidence,
        "escalated": response.escalate,
        "sources": response.sources,
        "ticket": response.ticket_created.model_dump() if response.ticket_created else None,
    }
