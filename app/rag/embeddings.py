"""Embedding utilities using free HuggingFace models."""
from functools import lru_cache
from typing import List

from langchain_community.embeddings import HuggingFaceEmbeddings

from app.config import settings


@lru_cache(maxsize=1)
def get_embedding_model() -> HuggingFaceEmbeddings:
    """
    Get the embedding model (cached singleton).
    Uses HuggingFace sentence-transformers which run locally for free.
    """
    return HuggingFaceEmbeddings(
        model_name=settings.embedding_model,
        model_kwargs={"device": "cpu"},  # Use CPU for free tier
        encode_kwargs={"normalize_embeddings": True},
    )


async def embed_text(text: str) -> List[float]:
    """Embed a single text string."""
    model = get_embedding_model()
    return model.embed_query(text)


async def embed_texts(texts: List[str]) -> List[List[float]]:
    """Embed multiple text strings."""
    model = get_embedding_model()
    return model.embed_documents(texts)
