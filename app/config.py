"""Application configuration using Pydantic Settings."""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings loaded from environment variables."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # App
    app_env: Literal["development", "staging", "production"] = "development"
    app_secret_key: str = "changeme"
    app_domain: str = "localhost:8000"
    debug: bool = True

    # LLM Provider
    llm_provider: Literal["groq", "google"] = "groq"
    groq_api_key: str = ""
    google_api_key: str = ""
    groq_model: str = "llama3-8b-8192"

    # Observability (LangSmith)
    langchain_api_key: str = ""
    langchain_tracing_v2: str = "false"
    langchain_project: str = "ai-support-agent"

    # Database
    database_url: str = "sqlite+aiosqlite:///./support_agent.db"
    mongodb_uri: str = ""
    mongodb_database: str = "support_agent_demo"

    # ChromaDB
    chroma_persist_directory: str = "./chroma_data"

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"

    # Demo channels
    enable_email_poller: bool = False
    email_poll_interval_seconds: int = 60

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
