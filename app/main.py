"""FastAPI application factory and main entry point."""
import asyncio
import contextlib
from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from app.api import api_router
from app.channels.email_handler import poll_inbox_async
from app.config import settings
from app.core.logging import get_logger
from app.models.base import init_db

logger = get_logger(__name__)

# Root of the project (one level above app/)
PROJECT_ROOT = Path(__file__).parent.parent


async def _email_poll_loop() -> None:
    while True:
        try:
            await poll_inbox_async()
        except Exception as exc:
            logger.warning("Email poll error", error=str(exc))

        await asyncio.sleep(max(5, settings.email_poll_interval_seconds))


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Application lifespan events."""
    logger.info("Starting AI Support Agent API", env=settings.app_env)

    await init_db()
    logger.info("Database initialized")

    poller_task = None
    if settings.enable_email_poller:
        poller_task = asyncio.create_task(_email_poll_loop())
        logger.info("Email poller started", interval=settings.email_poll_interval_seconds)

    yield

    if poller_task:
        poller_task.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await poller_task

    logger.info("Shutting down AI Support Agent API")


def create_app() -> FastAPI:
    """Create and configure the FastAPI application."""
    app = FastAPI(
        title="AI Customer Support Agent",
        description="Multi-channel AI customer support platform with RAG-powered responses",
        version="0.1.0",
        lifespan=lifespan,
        docs_url="/docs",
        redoc_url="/redoc",
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # ── Serve the interactive demo UI at the root URL ─────────────────────────
    @app.get("/", include_in_schema=False)
    async def serve_demo():
        demo_path = PROJECT_ROOT / "demo.html"
        if demo_path.exists():
            return FileResponse(str(demo_path), media_type="text/html")
        # Fallback to a basic redirect to /docs if demo.html is missing
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/docs")

    @app.get("/demo", include_in_schema=False)
    async def serve_demo_alias():
        """Alias — same as /"""
        demo_path = PROJECT_ROOT / "demo.html"
        if demo_path.exists():
            return FileResponse(str(demo_path), media_type="text/html")
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/docs")

    @app.get("/dataflow", include_in_schema=False)
    async def serve_dataflow():
        """Serve the system dataflow diagram."""
        path = PROJECT_ROOT / "system_dataflow.html"
        if path.exists():
            return FileResponse(str(path), media_type="text/html")
        from fastapi.responses import RedirectResponse
        return RedirectResponse("/docs")

    # ── All API routes ────────────────────────────────────────────────────────
    app.include_router(api_router)

    return app


app = create_app()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8001,
        reload=settings.is_development,
    )
