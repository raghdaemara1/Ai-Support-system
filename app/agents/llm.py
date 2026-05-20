"""LLM provider configuration - supports free tiers."""
from functools import lru_cache

from langchain_core.language_models import BaseChatModel

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

# Reliable Groq models with strong tool-calling support
_GROQ_FALLBACK_MODEL = "llama-3.3-70b-versatile"


@lru_cache(maxsize=1)
def get_llm() -> BaseChatModel:
    """
    Get the configured LLM based on settings.

    Supports:
    - Groq (free tier with Llama 3.3-70b)
    - Google Gemini (free tier available)
    """
    provider = settings.llm_provider

    if provider == "groq":
        from langchain_groq import ChatGroq

        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is required when using Groq provider")

        model = settings.groq_model or _GROQ_FALLBACK_MODEL
        logger.info("Using Groq LLM provider", model=model)
        return ChatGroq(
            api_key=settings.groq_api_key,
            model=model,
            temperature=0.1,
            max_tokens=2048,
        )

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when using Google provider")

        logger.info("Using Google Gemini provider", model="gemini-2.0-flash")
        return ChatGoogleGenerativeAI(
            google_api_key=settings.google_api_key,
            model="gemini-2.0-flash",
            temperature=0.1,
            max_output_tokens=2048,
        )

    elif provider == "ollama":
        from langchain_ollama import ChatOllama

        model = settings.ollama_model
        logger.info("Using Ollama local LLM provider", model=model)
        return ChatOllama(
            model=model,
            base_url=settings.ollama_base_url,
            temperature=0.1,
            num_predict=2048,
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def get_streaming_llm() -> BaseChatModel:
    """Get LLM configured for streaming responses."""
    provider = settings.llm_provider

    if provider == "groq":
        from langchain_groq import ChatGroq

        model = settings.groq_model or _GROQ_FALLBACK_MODEL
        return ChatGroq(
            api_key=settings.groq_api_key,
            model=model,
            temperature=0.1,
            max_tokens=2048,
            streaming=True,
        )

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            google_api_key=settings.google_api_key,
            model="gemini-2.0-flash",
            temperature=0.1,
            max_output_tokens=2048,
        )

    elif provider == "ollama":
        from langchain_ollama import ChatOllama

        model = settings.groq_model or "llama3.1"
        return ChatOllama(
            model=model,
            temperature=0.1,
            num_predict=2048,
            streaming=True,
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
