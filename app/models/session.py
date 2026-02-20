"""Conversation session model."""
from datetime import datetime
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, Float, ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin

if TYPE_CHECKING:
    from app.models.tenant import Tenant
    from app.models.message import Message


class ConversationSession(Base, UUIDMixin, TimestampMixin):
    """A conversation session between a customer and the AI agent."""

    __tablename__ = "conversation_sessions"

    tenant_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tenants.id"),
        nullable=False,
        index=True,
    )
    customer_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), nullable=False)  # voice, chat, email
    status: Mapped[str] = mapped_column(
        String(20),
        default="active",
    )  # active, resolved, escalated
    sentiment_score: Mapped[float] = mapped_column(Float, default=0.0)
    turn_count: Mapped[int] = mapped_column(Integer, default=0)
    containment_result: Mapped[str | None] = mapped_column(String(20), nullable=True)
    escalation_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    started_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=datetime.utcnow,
    )
    ended_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )

    # Relationships
    tenant: Mapped["Tenant"] = relationship("Tenant", back_populates="sessions")
    messages: Mapped[list["Message"]] = relationship(
        "Message",
        back_populates="session",
        lazy="selectin",
        order_by="Message.created_at",
    )

    def __repr__(self) -> str:
        return f"<ConversationSession(id={self.id}, channel={self.channel}, status={self.status})>"
