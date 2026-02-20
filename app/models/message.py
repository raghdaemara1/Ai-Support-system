"""Message model for conversation history."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.session import ConversationSession


class Message(Base, UUIDMixin, TimestampMixin):
    """A single message in a conversation session."""

    __tablename__ = "messages"

    session_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("conversation_sessions.id"),
        nullable=False,
        index=True,
    )
    role: Mapped[str] = mapped_column(String(20), nullable=False)  # user, assistant, system
    content: Mapped[str] = mapped_column(Text, nullable=False)
    tool_calls: Mapped[dict | None] = mapped_column(JSON, nullable=True)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)

    # Relationships
    session: Mapped["ConversationSession"] = relationship(
        "ConversationSession",
        back_populates="messages",
    )

    def __repr__(self) -> str:
        content_preview = self.content[:50] + "..." if len(self.content) > 50 else self.content
        return f"<Message(id={self.id}, role={self.role}, content='{content_preview}')>"
