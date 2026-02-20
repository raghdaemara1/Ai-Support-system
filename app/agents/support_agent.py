"""Main customer support agent."""
from typing import List

from langchain_core.tools import BaseTool

from app.agents.base_agent import BaseAgent
from app.agents.prompts.system_prompt import get_system_prompt
from app.tools.knowledge_base import search_knowledge_base
from app.tools.escalation_tools import escalate_to_human
from app.models.schemas import TenantConfig


class SupportAgent(BaseAgent):
    """
    Main customer support agent for chat interactions.

    This agent handles general customer inquiries using:
    - Knowledge base search for information retrieval
    - Escalation to human agents when needed
    """

    def _get_system_prompt(self) -> str:
        """Get the system prompt for the support agent."""
        return get_system_prompt(
            persona_name=self.tenant_config.persona_name,
            persona_description=self.tenant_config.persona_description,
            channel=self.channel,
            language=self.tenant_config.language,
        )

    def _get_tools(self) -> List[BaseTool]:
        """Get the tools available to this agent."""
        return [
            search_knowledge_base,
            escalate_to_human,
        ]


class VoiceAgent(BaseAgent):
    """
    Voice-optimized support agent for phone calls.

    Provides shorter, more conversational responses suitable for
    text-to-speech output.
    """

    def _get_system_prompt(self) -> str:
        """Get the voice-optimized system prompt."""
        from app.agents.prompts.voice_prompt import get_voice_prompt

        return get_voice_prompt(
            persona_name=self.tenant_config.persona_name,
            persona_description=self.tenant_config.persona_description,
            language=self.tenant_config.language,
        )

    def _get_tools(self) -> List[BaseTool]:
        """Get the tools available to the voice agent."""
        return [
            search_knowledge_base,
            escalate_to_human,
        ]


class EmailAgent(BaseAgent):
    """
    Email-optimized support agent.

    Provides longer, well-formatted responses suitable for
    email communication.
    """

    def _get_system_prompt(self) -> str:
        """Get the email-optimized system prompt."""
        from app.agents.prompts.email_prompt import get_email_prompt

        return get_email_prompt(
            persona_name=self.tenant_config.persona_name,
            persona_description=self.tenant_config.persona_description,
            language=self.tenant_config.language,
        )

    def _get_tools(self) -> List[BaseTool]:
        """Get the tools available to the email agent."""
        return [
            search_knowledge_base,
            escalate_to_human,
        ]


def get_agent_for_channel(
    channel: str,
    tenant_config: TenantConfig,
    tenant_id: str,
) -> BaseAgent:
    """
    Factory function to get the appropriate agent for a channel.

    Args:
        channel: The communication channel (chat, voice, email)
        tenant_config: Configuration for the tenant
        tenant_id: The tenant's unique identifier

    Returns:
        An agent instance appropriate for the channel
    """
    agents = {
        "chat": SupportAgent,
        "voice": VoiceAgent,
        "email": EmailAgent,
    }

    agent_class = agents.get(channel, SupportAgent)
    return agent_class(
        tenant_config=tenant_config,
        channel=channel,
        tenant_id=tenant_id,
    )
