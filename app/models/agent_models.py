from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field


class Channel(str, Enum):
    CHAT = "chat"
    VOICE = "voice"
    EMAIL = "email"


class MessageRole(str, Enum):
    USER = "user"
    AGENT = "agent"
    SYSTEM = "system"


class Message(BaseModel):
    id: str
    session_id: str
    role: MessageRole
    content: str
    channel: Channel
    timestamp: datetime = Field(default_factory=datetime.utcnow)
    metadata: dict = Field(default_factory=dict)


class Session(BaseModel):
    session_id: str
    channel: Channel
    user_id: str | None = None
    machine: str | None = None
    history: list[Message] = Field(default_factory=list)
    escalated: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)


class Ticket(BaseModel):
    ticket_id: str
    session_id: str
    channel: Channel
    summary: str
    machine: str | None = None
    alarm_code: str | None = None
    priority: Literal["low", "medium", "high", "critical"] = "medium"
    status: Literal["open", "in_progress", "resolved", "escalated"] = "open"
    created_at: datetime = Field(default_factory=datetime.utcnow)


class AgentResponse(BaseModel):
    session_id: str
    content: str
    confidence: float = 1.0
    intent: str | None = None
    tool_used: str | None = None
    escalate: bool = False
    ticket_created: Ticket | None = None
    sources: list[str] = Field(default_factory=list)


class KBSearchResult(BaseModel):
    alarm_id: str | None = None
    description: str
    cause: str | None = None
    action: str | None = None
    machine: str | None = None
    score: float
