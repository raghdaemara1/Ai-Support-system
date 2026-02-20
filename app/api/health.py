"""Health check endpoints."""
from fastapi import APIRouter

from app.config import settings
from app.models.schemas import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """Check API health status."""
    return HealthResponse(
        status="healthy",
        version="0.1.0",
        llm_provider=settings.llm_provider,
        database="sqlite",
    )


@router.get("/")
async def root():
    """Root endpoint."""
    return {
        "name": "AI Customer Support Agent",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
    }
