"""Base agent class with common functionality."""
from abc import ABC, abstractmethod
from typing import Any, AsyncIterator, List

from langchain_core.messages import AIMessage, BaseMessage, HumanMessage, SystemMessage
from langgraph.prebuilt import create_react_agent

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
        self._graph = self._build_graph()

    @abstractmethod
    def _get_system_prompt(self) -> str:
        """Return channel-specific system prompt."""
        ...

    @abstractmethod
    def _get_tools(self) -> list:
        """Return list of LangChain tools for this channel."""
        ...

    def _build_graph(self):
        """Build the LangGraph react agent (LangChain 1.x compatible)."""
        llm = get_llm()
        tools = self._get_tools()
        system_prompt = self._get_system_prompt()

        return create_react_agent(
            model=llm,
            tools=tools,
            prompt=SystemMessage(content=system_prompt),
        )

    # ── Compiled config: cap recursion so tool-call loops always terminate ──
    _GRAPH_CONFIG = {"recursion_limit": 4}

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
            **kwargs: Additional arguments

        Returns:
            dict containing 'output' key with the agent's text response
        """
        logger.debug(
            "Agent invoked",
            channel=self.channel,
            tenant_id=self.tenant_id,
            input_length=len(user_input),
        )

        messages = list(history) + [HumanMessage(content=user_input)]
        result = await self._graph.ainvoke(
            {"messages": messages},
            config=self._GRAPH_CONFIG,
        )

        # Extract last AI message as output, stripping malformed tool-call
        # artifacts that some models emit as raw text content.
        import re as _re, json as _json
        output = ""
        for msg in reversed(result.get("messages", [])):
            if isinstance(msg, AIMessage) and msg.content:
                text = msg.content
                # Strip trailing <function=...> bleed
                text = _re.sub(r'\s*<function=[^>]*>.*', '', text, flags=_re.DOTALL)
                
                # Strip markdown blocks if present
                clean_for_json = _re.sub(r'^```(?:json)?\s*', '', text)
                clean_for_json = _re.sub(r'\s*```$', '', clean_for_json).strip()
                
                # Strip {"name": ...} tool-call JSON that leaked as text
                text = _re.sub(r'\s*(?:```(?:json)?\s*)?\{\s*"name"\s*:.*', '', text, flags=_re.DOTALL)
                text = text.strip()
                
                # Skip messages that are ONLY a tool-call JSON (whole content replaced)
                if not text:
                    continue
                    
                # Also skip if the whole message is valid JSON with "name" key (Llama 4 leak)
                try:
                    parsed = _json.loads(clean_for_json)
                    if isinstance(parsed, dict) and "name" in parsed:
                        continue
                except Exception:
                    pass
                output = text
                break
                
        if not output:
            output = "I'm having a bit of trouble connecting to my tools right now. Could you please rephrase your request?"

        logger.debug(
            "Agent response",
            channel=self.channel,
            output_length=len(output),
        )

        return {"output": output, "messages": result.get("messages", [])}

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
        messages = list(history) + [HumanMessage(content=user_input)]
        async for chunk in self._graph.astream({"messages": messages}):
            if "agent" in chunk:
                for msg in chunk["agent"].get("messages", []):
                    if isinstance(msg, AIMessage) and msg.content:
                        yield {"output": msg.content}


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
