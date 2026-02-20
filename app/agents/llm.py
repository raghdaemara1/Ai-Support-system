"""LLM provider configuration - supports free tiers."""
from functools import lru_cache
from typing import Any

from langchain_core.language_models import BaseChatModel

from app.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


@lru_cache(maxsize=1)
def get_llm() -> BaseChatModel:
    """
    Get the configured LLM based on settings.

    Supports:
    - Groq (free tier with Llama 3.1/3.3)
    - Google Gemini (free tier available)
    """
    provider = settings.llm_provider

    if provider == "groq":
        from langchain_groq import ChatGroq

        if not settings.groq_api_key:
            raise ValueError("GROQ_API_KEY is required when using Groq provider")

        logger.info("Using Groq LLM provider", model="llama-3.3-70b-versatile")
        return ChatGroq(
            api_key=settings.groq_api_key,
            model="llama-3.3-70b-versatile",  # Free tier model
            temperature=0.1,
            max_tokens=1024,
        )

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        if not settings.google_api_key:
            raise ValueError("GOOGLE_API_KEY is required when using Google provider")

        logger.info("Using Google Gemini Pro LLM provider", model="gemini-2.0-flash")
        return ChatGoogleGenerativeAI(
            google_api_key=settings.google_api_key,
            model="gemini-2.0-flash",  # Gemini Pro model
            temperature=0.1,
            max_output_tokens=2048,
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")


def get_streaming_llm() -> BaseChatModel:
    """Get LLM configured for streaming responses."""
    provider = settings.llm_provider

    if provider == "groq":
        from langchain_groq import ChatGroq

        return ChatGroq(
            api_key=settings.groq_api_key,
            model="llama-3.3-70b-versatile",
            temperature=0.1,
            max_tokens=1024,
            streaming=True,
        )

    elif provider == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI

        return ChatGoogleGenerativeAI(
            google_api_key=settings.google_api_key,
            model="gemini-2.0-flash",  # Gemini Pro model
            temperature=0.1,
            max_output_tokens=2048,
        )

    else:
        raise ValueError(f"Unknown LLM provider: {provider}")
