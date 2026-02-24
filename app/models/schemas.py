"""Pydantic schemas for request/response validation."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


# Tenant Schemas
class TenantConfig(BaseModel):
    """Configuration for a tenant's AI agent."""
    persona_name: str = "Aria"
    persona_description: str = "A helpful AI support agent."
    escalation_keywords: list[str] = Field(default_factory=list)
    max_turns_before_escalate: int = 10
    channels: list[str] = Field(default_factory=lambda: ["chat"])
    language: str = "en"
    sentiment_threshold: float = -0.7


class TenantCreate(BaseModel):
    """Request schema for creating a tenant."""
    name: str
    slug: str
    config: TenantConfig = Field(default_factory=TenantConfig)


class TenantResponse(BaseModel):
    """Response schema for tenant."""
    id: str
    name: str
    slug: str
    config: dict
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


# Chat Schemas
class ChatRequest(BaseModel):
    """Request schema for chat messages."""
    tenant_id: str
    customer_id: str
    session_id: str | None = None
    message: str
    metadata: dict = Field(default_factory=dict)


class EmailRequest(BaseModel):
    """Request schema for inbound email from the UI."""
    tenant_id: str
    customer_email: str
    subject: str
    body: str


class ChatResponse(BaseModel):
    """Response schema for chat messages."""
    session_id: str
    message: str
    escalated: bool = False
    escalation_reason: str | None = None
    sources: list[str] = Field(default_factory=list)


class ChatStreamToken(BaseModel):
    """Schema for streaming chat tokens."""
    type: Literal["token", "done", "error", "sources"]
    content: str = ""
    sources: list[str] = Field(default_factory=list)


# Session Schemas
class SessionResponse(BaseModel):
    """Response schema for conversation session."""
    id: str
    tenant_id: str
    customer_id: str
    channel: str
    status: str
    sentiment_score: float
    turn_count: int
    started_at: datetime
    ended_at: datetime | None = None

    class Config:
        from_attributes = True


# Message Schemas
class MessageResponse(BaseModel):
    """Response schema for messages."""
    id: str
    role: str
    content: str
    created_at: datetime

    class Config:
        from_attributes = True


# Knowledge Base Schemas
class KnowledgeSource(BaseModel):
    """Schema for a knowledge source."""
    type: Literal["pdf", "url", "text"]
    source_name: str
    path: str | None = None
    url: str | None = None
    content: str | None = None


class IngestionRequest(BaseModel):
    """Request schema for knowledge ingestion."""
    sources: list[KnowledgeSource]


class IngestionResponse(BaseModel):
    """Response schema for knowledge ingestion."""
    status: str
    chunks_ingested: int
    sources_processed: int


# Health Check
class HealthResponse(BaseModel):
    """Response schema for health check."""
    status: str
    version: str = "0.1.0"
    llm_provider: str
    database: str
