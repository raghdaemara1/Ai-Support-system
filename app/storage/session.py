import uuid
from datetime import datetime

from app.models.agent_models import Channel, Message, MessageRole, Session


class SessionManager:
    """In-memory session manager for demo and local development."""

    def __init__(self):
        self._sessions: dict[str, Session] = {}

    def get_or_create(self, session_id: str, channel: str, user_id: str | None = None) -> Session:
        session = self._sessions.get(session_id)
        if session:
            session.last_active = datetime.utcnow()
            return session

        created = Session(session_id=session_id, channel=Channel(channel), user_id=user_id)
        self._sessions[session_id] = created
        return created

    def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        metadata: dict | None = None,
    ) -> Message:
        session = self._sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        try:
            parsed_role = MessageRole(role)
        except ValueError:
            parsed_role = MessageRole.USER

        message = Message(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role=parsed_role,
            content=content,
            channel=session.channel,
            metadata=metadata or {},
        )
        session.history.append(message)
        session.last_active = datetime.utcnow()
        return message
