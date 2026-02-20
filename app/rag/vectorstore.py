"""ChromaDB vector store setup - free local vector database."""
from functools import lru_cache
from pathlib import Path

import chromadb
from chromadb.config import Settings as ChromaSettings
from langchain_community.vectorstores import Chroma

from app.config import settings
from app.rag.embeddings import get_embedding_model


def get_chroma_client() -> chromadb.Client:
    """Get ChromaDB client with persistent storage."""
    persist_dir = Path(settings.chroma_persist_directory)
    persist_dir.mkdir(parents=True, exist_ok=True)

    return chromadb.Client(
        ChromaSettings(
            chroma_db_impl="duckdb+parquet",
            persist_directory=str(persist_dir),
            anonymized_telemetry=False,
        )
    )


def get_vectorstore(tenant_id: str) -> Chroma:
    """
    Get a Chroma vectorstore for a specific tenant.
    Each tenant gets their own collection for data isolation.
    """
    persist_dir = Path(settings.chroma_persist_directory)
    persist_dir.mkdir(parents=True, exist_ok=True)

    return Chroma(
        collection_name=f"tenant_{tenant_id}",
        embedding_function=get_embedding_model(),
        persist_directory=str(persist_dir),
    )


def get_or_create_collection(tenant_id: str) -> Chroma:
    """Get or create a vector store collection for a tenant."""
    return get_vectorstore(tenant_id)
