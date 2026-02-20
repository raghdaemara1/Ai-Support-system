"""Tenant (enterprise customer) model."""
from sqlalchemy import Boolean, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base, TimestampMixin, UUIDMixin


class Tenant(Base, UUIDMixin, TimestampMixin):
    """Tenant represents an enterprise customer using the platform."""

    __tablename__ = "tenants"

    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    api_key_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    config: Mapped[dict] = mapped_column(JSON, default=dict)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)

    # Relationships
    sessions: Mapped[list["ConversationSession"]] = relationship(
        "ConversationSession",
        back_populates="tenant",
        lazy="selectin",
    )

    def __repr__(self) -> str:
        return f"<Tenant(id={self.id}, name={self.name}, slug={self.slug})>"

    @property
    def persona_name(self) -> str:
        return self.config.get("persona_name", "Aria")

    @property
    def persona_description(self) -> str:
        return self.config.get("persona_description", "A helpful AI support agent.")

    @property
    def escalation_keywords(self) -> list[str]:
        return self.config.get("escalation_keywords", [])

    @property
    def max_turns_before_escalate(self) -> int:
        return self.config.get("max_turns_before_escalate", 10)

    @property
    def channels(self) -> list[str]:
        return self.config.get("channels", ["chat"])

    @property
    def language(self) -> str:
        return self.config.get("language", "en")

    @property
    def sentiment_threshold(self) -> float:
        return self.config.get("sentiment_threshold", -0.7)
