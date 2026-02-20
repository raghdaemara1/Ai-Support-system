"""Session management service."""
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.session import ConversationSession
from app.models.message import Message
from app.core.logging import get_logger

logger = get_logger(__name__)

# In-memory session cache for fast access (replaces Redis for free tier)
_session_cache: dict[str, dict] = {}
_message_cache: dict[str, List[dict]] = {}


class SessionService:
    """Service for managing conversation sessions."""

    def __init__(self, db: AsyncSession):
        self.db = db

    async def create_session(
        self,
        tenant_id: str,
        customer_id: str,
        channel: str,
    ) -> ConversationSession:
        """Create a new conversation session."""
        session = ConversationSession(
            id=str(uuid.uuid4()),
            tenant_id=tenant_id,
            customer_id=customer_id,
            channel=channel,
            status="active",
            started_at=datetime.now(timezone.utc),
        )

        self.db.add(session)
        await self.db.commit()
        await self.db.refresh(session)

        # Cache the session
        _session_cache[session.id] = {
            "id": session.id,
            "tenant_id": tenant_id,
            "customer_id": customer_id,
            "channel": channel,
            "status": "active",
        }
        _message_cache[session.id] = []

        logger.info(
            "Created session",
            session_id=session.id,
            tenant_id=tenant_id,
            channel=channel,
        )

        return session

    async def get_session(self, session_id: str) -> Optional[ConversationSession]:
        """Get a session by ID."""
        result = await self.db.execute(
            select(ConversationSession).where(ConversationSession.id == session_id)
        )
        return result.scalar_one_or_none()

    async def get_or_create_session(
        self,
        tenant_id: str,
        customer_id: str,
        channel: str,
        session_id: Optional[str] = None,
    ) -> ConversationSession:
        """Get existing session or create new one."""
        if session_id:
            session = await self.get_session(session_id)
            if session and session.status == "active":
                return session

        # Check for existing active session
        result = await self.db.execute(
            select(ConversationSession).where(
                ConversationSession.tenant_id == tenant_id,
                ConversationSession.customer_id == customer_id,
                ConversationSession.channel == channel,
                ConversationSession.status == "active",
            )
        )
        session = result.scalar_one_or_none()

        if session:
            return session

        return await self.create_session(tenant_id, customer_id, channel)

    async def add_message(
        self,
        session_id: str,
        role: str,
        content: str,
        tool_calls: dict | None = None,
        latency_ms: int | None = None,
    ) -> Message:
        """Add a message to a session."""
        message = Message(
            id=str(uuid.uuid4()),
            session_id=session_id,
            role=role,
            content=content,
            tool_calls=tool_calls,
            latency_ms=latency_ms,
        )

        self.db.add(message)

        # Update session turn count
        session = await self.get_session(session_id)
        if session:
            session.turn_count += 1

        await self.db.commit()
        await self.db.refresh(message)

        # Cache the message
        if session_id not in _message_cache:
            _message_cache[session_id] = []
        _message_cache[session_id].append({
            "role": role,
            "content": content,
        })

        return message

    async def get_history(
        self,
        session_id: str,
        limit: int = 20,
    ) -> List[BaseMessage]:
        """Get conversation history as LangChain messages."""
        # Try cache first
        if session_id in _message_cache:
            messages = _message_cache[session_id][-limit:]
        else:
            # Load from database
            result = await self.db.execute(
                select(Message)
                .where(Message.session_id == session_id)
                .order_by(Message.created_at.desc())
                .limit(limit)
            )
            db_messages = result.scalars().all()
            messages = [{"role": m.role, "content": m.content} for m in reversed(db_messages)]

        # Convert to LangChain messages
        lc_messages = []
        for msg in messages:
            if msg["role"] == "user":
                lc_messages.append(HumanMessage(content=msg["content"]))
            elif msg["role"] == "assistant":
                lc_messages.append(AIMessage(content=msg["content"]))

        return lc_messages

    async def close_session(
        self,
        session_id: str,
        containment_result: str = "resolved",
    ) -> None:
        """Close a session."""
        session = await self.get_session(session_id)
        if session:
            session.status = "resolved"
            session.containment_result = containment_result
            session.ended_at = datetime.now(timezone.utc)
            await self.db.commit()

            # Update cache
            if session_id in _session_cache:
                _session_cache[session_id]["status"] = "resolved"

            logger.info("Closed session", session_id=session_id, result=containment_result)

    async def escalate_session(
        self,
        session_id: str,
        reason: str,
    ) -> None:
        """Mark a session as escalated."""
        session = await self.get_session(session_id)
        if session:
            session.status = "escalated"
            session.containment_result = "escalated"
            session.escalation_reason = reason
            await self.db.commit()

            logger.info("Escalated session", session_id=session_id, reason=reason)
