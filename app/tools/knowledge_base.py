"""Knowledge base search tool and tenant-bound tool factory."""
from langchain.tools import tool

from app.rag.retriever import retrieve
from app.core.logging import get_logger

logger = get_logger(__name__)


def make_search_tool(tenant_id: str):
    """
    Return a search_knowledge_base tool bound to a specific tenant.
    The tenant_id is captured via closure — the LLM only needs to provide
    the search query, not the tenant ID.
    """

    @tool
    async def search_knowledge_base(query: str) -> str:
        """
        Search the company knowledge base for relevant information.

        Use this tool to find answers about:
        - Product information and features
        - Company policies and procedures
        - Troubleshooting steps and guides
        - Frequently asked questions

        Always search here FIRST before using other tools or saying you don't know.

        Args:
            query: The search query describing what information you need

        Returns:
            Relevant information from the knowledge base, or a message if nothing found.
        """
        try:
            results = await retrieve(query=query, tenant_id=tenant_id, k=4)

            if not results:
                return "No relevant information found in the knowledge base for this query."

            formatted_results = []
            for i, doc in enumerate(results, 1):
                source = doc.metadata.get("source", "internal")
                content = doc.page_content.strip()
                formatted_results.append(f"[Source {i}: {source}]\n{content}")

            return "\n\n---\n\n".join(formatted_results)

        except Exception as e:
            logger.error("Knowledge base search failed", query=query, error=str(e))
            return f"Error searching knowledge base: {str(e)}"

    return search_knowledge_base
