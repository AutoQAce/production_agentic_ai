"""FastAPI application entrypoint — Layer 0 (Foundation).

App factory + structured logging/request tracing + custom exception handling (Layer 6,
built ahead of schedule — see AGENTIC_AI_PRODUCTION_BIBLE.md Appendix C) + CORS + a health
check. Later layers bolt on here — the API gateway routers (Layer 5), Prometheus middleware,
rate limiting and auth (Layer 2), and the lifespan hooks that open/close the DB pool and LLM
service (Layers 1, 3).
"""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.exception_handlers import handle_app_exception, handle_unhandled_exception
from app.core.exceptions import AppException
from app.core.logging import configure_logging, get_logger
from app.core.middleware import RequestContextMiddleware

logger = get_logger(__name__)


def create_app() -> FastAPI:
    """Application factory — build and configure the FastAPI instance."""
    settings = get_settings()
    configure_logging(settings)

    app = FastAPI(
        title=settings.PROJECT_NAME,
        version=settings.VERSION,
        debug=settings.DEBUG,
    )

    app.add_middleware(RequestContextMiddleware)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.allowed_origins_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    app.add_exception_handler(AppException, handle_app_exception)
    app.add_exception_handler(Exception, handle_unhandled_exception)

    @app.get("/health", tags=["ops"])
    def health() -> dict[str, str]:
        """Liveness probe used by Docker/Azure and the stress test."""
        logger.info("health_check_invoked")
        return {"status": "ok", "env": settings.APP_ENV, "version": settings.VERSION}

    return app


app = create_app()
