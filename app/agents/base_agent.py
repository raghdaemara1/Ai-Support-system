"""Base agent class with common functionality."""
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, List

from langchain.agents import AgentExecutor, create_tool_calling_agent
from langchain_core.messages import AIMessage, BaseMessage, HumanMessage
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from app.agents.llm import get_llm
from app.core.logging import get_logger
from app.models.schemas import TenantConfig

logger = get_logger(__name__)


class BaseAgent(ABC):
    """Abstract base class for all agents."""

    def __init__(
        self,
        tenant_config: TenantConfig,
        channel: str,
        tenant_id: str,
    ):
        self.tenant_config = tenant_config
        self.channel = channel
        self.tenant_id = tenant_id
        self.executor: AgentExecutor = self._build_executor()

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Return channel-specific system prompt."""
        ...

    @abstractmethod
    def _get_tools(self) -> list:
        """Return list of LangChain tools for this channel."""
        ...

    def _build_executor(self) -> AgentExecutor:
        """Build the LangChain agent executor."""
        llm = get_llm()
        tools = self._get_tools()

        prompt = ChatPromptTemplate.from_messages([
            ("system", self._get_system_prompt()),
            MessagesPlaceholder("chat_history"),
            ("human", "{input}"),
            MessagesPlaceholder("agent_scratchpad"),
        ])

        agent = create_tool_calling_agent(llm, tools, prompt)

        return AgentExecutor(
            agent=agent,
            tools=tools,
            max_iterations=5,
            early_stopping_method="generate",
            verbose=True,
            handle_parsing_errors=True,
        )

    async def invoke(
        self,
        user_input: str,
        history: List[BaseMessage],
        **kwargs,
    ) -> dict[str, Any]:
        """
        Process a user message and return the agent's response.

        Args:
            user_input: The user's message
            history: List of previous messages in the conversation
            **kwargs: Additional arguments passed to the executor

        Returns:
            dict containing 'output' and any tool call information
        """
        logger.debug(
            "Agent invoked",
            channel=self.channel,
            tenant_id=self.tenant_id,
            input_length=len(user_input),
        )

        result = await self.executor.ainvoke({
            "input": user_input,
            "chat_history": history,
            "tenant_id": self.tenant_id,
            **kwargs,
        })

        logger.debug(
            "Agent response",
            channel=self.channel,
            output_length=len(result.get("output", "")),
        )

        return result

    async def astream(
        self,
        user_input: str,
        history: List[BaseMessage],
        **kwargs,
    ) -> AsyncIterator[dict[str, Any]]:
        """
        Stream the agent's response token by token.

        Args:
            user_input: The user's message
            history: List of previous messages
            **kwargs: Additional arguments

        Yields:
            dict chunks containing partial output
        """
        async for chunk in self.executor.astream({
            "input": user_input,
            "chat_history": history,
            "tenant_id": self.tenant_id,
            **kwargs,
        }):
            yield chunk


def messages_to_langchain(messages: List[dict]) -> List[BaseMessage]:
    """Convert message dicts to LangChain message objects."""
    result = []
    for msg in messages:
        role = msg.get("role", "user")
        content = msg.get("content", "")

        if role == "user":
            result.append(HumanMessage(content=content))
        elif role == "assistant":
            result.append(AIMessage(content=content))
        # Skip system messages in history

    return result
