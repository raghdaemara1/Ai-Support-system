"""Agent prompt templates."""
from app.agents.prompts.system_prompt import get_system_prompt
from app.agents.prompts.voice_prompt import get_voice_prompt
from app.agents.prompts.email_prompt import get_email_prompt

__all__ = ["get_system_prompt", "get_voice_prompt", "get_email_prompt"]
