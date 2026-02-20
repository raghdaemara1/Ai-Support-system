"""Structured logging configuration."""
import structlog
from app.config import settings


def get_logger(name: str = __name__) -> structlog.BoundLogger:
    """Get a configured structured logger."""
    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.StackInfoRenderer(),
            structlog.dev.set_exc_info,
            structlog.processors.TimeStamper(fmt="iso"),
            (
                structlog.dev.ConsoleRenderer()
                if settings.is_development
                else structlog.processors.JSONRenderer()
            ),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            logging_level="DEBUG" if settings.debug else "INFO"
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )
    return structlog.get_logger(name)


logger = get_logger()
