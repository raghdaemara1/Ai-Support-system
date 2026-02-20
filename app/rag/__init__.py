"""RAG (Retrieval-Augmented Generation) pipeline."""
from app.rag.retriever import retrieve, get_retriever
from app.rag.ingestion import ingest_documents

__all__ = ["retrieve", "get_retriever", "ingest_documents"]
