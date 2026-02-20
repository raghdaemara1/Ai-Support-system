"""Retrieval logic for RAG pipeline."""
from typing import List

from langchain_core.documents import Document
from langchain_core.retrievers import BaseRetriever

from app.core.logging import get_logger
from app.rag.vectorstore import get_vectorstore

logger = get_logger(__name__)


def get_retriever(tenant_id: str, k: int = 4) -> BaseRetriever:
    """
    Get a retriever for a specific tenant's knowledge base.

    Args:
        tenant_id: Tenant identifier (collection name)
        k: Number of documents to retrieve

    Returns:
        LangChain retriever instance
    """
    vectorstore = get_vectorstore(tenant_id)

    return vectorstore.as_retriever(
        search_type="similarity",
        search_kwargs={"k": k},
    )


async def retrieve(
    query: str,
    tenant_id: str,
    k: int = 4,
) -> List[Document]:
    """
    Retrieve relevant documents for a query.

    Args:
        query: Search query
        tenant_id: Tenant identifier for namespace isolation
        k: Number of documents to retrieve

    Returns:
        List of relevant documents
    """
    try:
        vectorstore = get_vectorstore(tenant_id)
        docs = vectorstore.similarity_search(query, k=k)

        logger.debug(
            "Retrieved documents",
            query=query[:100],
            tenant_id=tenant_id,
            num_results=len(docs),
        )

        return docs

    except Exception as e:
        logger.error(
            "Retrieval failed",
            query=query[:100],
            tenant_id=tenant_id,
            error=str(e),
        )
        return []


async def retrieve_with_scores(
    query: str,
    tenant_id: str,
    k: int = 4,
    score_threshold: float = 0.5,
) -> List[tuple[Document, float]]:
    """
    Retrieve documents with relevance scores.

    Args:
        query: Search query
        tenant_id: Tenant identifier
        k: Number of documents to retrieve
        score_threshold: Minimum similarity score (0-1)

    Returns:
        List of (document, score) tuples
    """
    try:
        vectorstore = get_vectorstore(tenant_id)
        results = vectorstore.similarity_search_with_score(query, k=k)

        # Filter by score threshold
        filtered = [(doc, score) for doc, score in results if score >= score_threshold]

        logger.debug(
            "Retrieved documents with scores",
            query=query[:100],
            tenant_id=tenant_id,
            num_results=len(filtered),
        )

        return filtered

    except Exception as e:
        logger.error(
            "Retrieval with scores failed",
            query=query[:100],
            tenant_id=tenant_id,
            error=str(e),
        )
        return []
