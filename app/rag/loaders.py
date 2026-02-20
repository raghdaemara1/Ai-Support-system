"""Document loaders for different source types."""
import asyncio
from pathlib import Path
from typing import List

from langchain_core.documents import Document
from langchain_community.document_loaders import (
    PyPDFLoader,
    WebBaseLoader,
    TextLoader,
)

from app.core.logging import get_logger

logger = get_logger(__name__)


async def load_pdf(path: str, source_name: str) -> List[Document]:
    """Load documents from a PDF file."""
    try:
        loader = PyPDFLoader(path)
        docs = await asyncio.to_thread(loader.load)
        for doc in docs:
            doc.metadata["source"] = source_name
            doc.metadata["type"] = "pdf"
        logger.info("Loaded PDF", path=path, num_pages=len(docs))
        return docs
    except Exception as e:
        logger.error("Failed to load PDF", path=path, error=str(e))
        return []


async def load_url(url: str, source_name: str) -> List[Document]:
    """Load documents from a web URL."""
    try:
        loader = WebBaseLoader(url)
        docs = await asyncio.to_thread(loader.load)
        for doc in docs:
            doc.metadata["source"] = source_name
            doc.metadata["type"] = "url"
            doc.metadata["url"] = url
        logger.info("Loaded URL", url=url, num_docs=len(docs))
        return docs
    except Exception as e:
        logger.error("Failed to load URL", url=url, error=str(e))
        return []


async def load_text(content: str, source_name: str) -> List[Document]:
    """Create documents from raw text content."""
    doc = Document(
        page_content=content,
        metadata={"source": source_name, "type": "text"},
    )
    return [doc]


async def load_text_file(path: str, source_name: str) -> List[Document]:
    """Load documents from a text file."""
    try:
        loader = TextLoader(path)
        docs = await asyncio.to_thread(loader.load)
        for doc in docs:
            doc.metadata["source"] = source_name
            doc.metadata["type"] = "text_file"
        logger.info("Loaded text file", path=path, num_docs=len(docs))
        return docs
    except Exception as e:
        logger.error("Failed to load text file", path=path, error=str(e))
        return []


async def load_documents(sources: List[dict]) -> List[Document]:
    """
    Load documents from multiple sources.

    sources format:
    [
        {"type": "pdf", "path": "/path/to/doc.pdf", "source_name": "manual"},
        {"type": "url", "url": "https://example.com/faq", "source_name": "faq"},
        {"type": "text", "content": "Some text...", "source_name": "custom"},
    ]
    """
    all_docs = []

    for source in sources:
        source_type = source.get("type")
        source_name = source.get("source_name", "unknown")

        if source_type == "pdf":
            docs = await load_pdf(source["path"], source_name)
        elif source_type == "url":
            docs = await load_url(source["url"], source_name)
        elif source_type == "text":
            docs = await load_text(source["content"], source_name)
        elif source_type == "text_file":
            docs = await load_text_file(source["path"], source_name)
        else:
            logger.warning("Unknown source type", source_type=source_type)
            continue

        all_docs.extend(docs)

    return all_docs
