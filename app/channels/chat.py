from fastapi import WebSocket

from app.agent.support_agent import SupportAgent
from app.storage.session import SessionManager

_session_manager = SessionManager()
_agent: SupportAgent | None = None


def _get_agent() -> SupportAgent:
    global _agent
    if _agent is None:
        _agent = SupportAgent()
    return _agent


async def chat_websocket_handler(websocket: WebSocket, session_id: str):
    await websocket.accept()
    session = _session_manager.get_or_create(session_id=session_id, channel="chat")

    try:
        while True:
            data = await websocket.receive_json()
            user_text = data.get("message", "")
            if not user_text:
                continue

            _session_manager.add_message(session_id, role="user", content=user_text)
            response = await _get_agent().respond(message=user_text, session=session)
            _session_manager.add_message(session_id, role="agent", content=response.content)

            await websocket.send_json(
                {
                    "message": response.content,
                    "intent": response.intent,
                    "confidence": response.confidence,
                    "escalated": response.escalate,
                    "sources": response.sources,
                    "ticket": response.ticket_created.model_dump() if response.ticket_created else None,
                }
            )

            if response.escalate:
                await websocket.send_json(
                    {
                        "message": "Connecting you to a human engineer now...",
                        "escalated": True,
                    }
                )
                break
    except Exception as exc:
        await websocket.send_json({"error": str(exc)})
    finally:
        await websocket.close()
