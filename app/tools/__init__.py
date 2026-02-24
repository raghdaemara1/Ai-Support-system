"""LangChain tool definitions for the support agent."""
from app.tools.knowledge_base import make_search_tool
from app.tools.escalation_tools import escalate_to_human

__all__ = [
    "make_search_tool",
    "escalate_to_human",
]
