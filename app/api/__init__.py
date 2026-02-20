"""API route handlers."""
from fastapi import APIRouter

from app.api.health import router as health_router
from app.api.chat import router as chat_router
from app.api.admin import router as admin_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])

__all__ = ["api_router"]
