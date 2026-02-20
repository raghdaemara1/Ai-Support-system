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

    # Database
    database_url: str = "sqlite+aiosqlite:///./support_agent.db"

    # ChromaDB
    chroma_persist_directory: str = "./chroma_data"

    # Embeddings
    embedding_model: str = "all-MiniLM-L6-v2"

    @property
    def is_development(self) -> bool:
        return self.app_env == "development"


@lru_cache
def get_settings() -> Settings:
    """Get cached settings instance."""
    return Settings()


settings = get_settings()
