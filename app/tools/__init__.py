"""LangChain tool definitions for the support agent."""
from app.tools.knowledge_base import search_knowledge_base
from app.tools.escalation_tools import escalate_to_human

__all__ = [
    "search_knowledge_base",
    "escalate_to_human",
]
