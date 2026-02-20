"""Channel router for directing messages to appropriate agents."""
from typing import Literal

from app.agents.support_agent import get_agent_for_channel, BaseAgent
from app.models.schemas import TenantConfig
from app.core.logging import get_logger

logger = get_logger(__name__)

ChannelType = Literal["chat", "voice", "email"]


class ChannelRouter:
    """
    Routes messages to the appropriate agent based on channel.

    Each channel may have different agent configurations optimized
    for that communication medium.
    """

    def __init__(self, tenant_config: TenantConfig, tenant_id: str):
        self.tenant_config = tenant_config
        self.tenant_id = tenant_id
        self._agents: dict[str, BaseAgent] = {}

    def get_agent(self, channel: ChannelType) -> BaseAgent:
        """
        Get or create an agent for the specified channel.

        Args:
            channel: The communication channel (chat, voice, email)

        Returns:
            An agent instance configured for the channel
        """
        if channel not in self._agents:
            self._agents[channel] = get_agent_for_channel(
                channel=channel,
                tenant_config=self.tenant_config,
                tenant_id=self.tenant_id,
            )
            logger.debug("Created agent for channel", channel=channel, tenant_id=self.tenant_id)

        return self._agents[channel]

    def is_channel_enabled(self, channel: ChannelType) -> bool:
        """Check if a channel is enabled for this tenant."""
        return channel in self.tenant_config.channels

    @property
    def enabled_channels(self) -> list[str]:
        """Get list of enabled channels."""
        return self.tenant_config.channels
