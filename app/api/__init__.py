"""API route handlers."""
from fastapi import APIRouter

from app.api.admin import router as admin_router
from app.api.chat import router as chat_router
from app.api.demo import router as demo_router
from app.api.health import router as health_router
from app.api.voice import router as twilio_voice_router
from app.channels.voice import router as voice_router

api_router = APIRouter()

api_router.include_router(health_router, tags=["health"])
api_router.include_router(chat_router, prefix="/chat", tags=["chat"])
api_router.include_router(admin_router, prefix="/admin", tags=["admin"])

# Spec-aligned demo surfaces from ai_support.md
api_router.include_router(demo_router, tags=["demo"])
api_router.include_router(voice_router, prefix="/api", tags=["voice"])
api_router.include_router(twilio_voice_router, prefix="/api/twilio", tags=["twilio_voice"])

__all__ = ["api_router"]
