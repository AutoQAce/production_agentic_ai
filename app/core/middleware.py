"""Per-request context binding + request lifecycle logging — Bible Step 7 (Observability).

One job: bind a request_id/method/path to structlog's contextvars for the life of one request and
emit start/finish/failure events. Does not configure logging (`logging.py`'s job) and does not
decide how to render an exception into an HTTP response (`exception_handlers.py`'s job) — it only
re-raises so FastAPI's exception-handling machinery can take over (SRP).
"""

from __future__ import annotations

import time
import uuid

import structlog
from starlette.middleware.base import BaseHTTPMiddleware, RequestResponseEndpoint
from starlette.requests import Request
from starlette.responses import Response

from app.core.logging import get_logger

logger = get_logger(__name__)


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Binds a request_id + method/path to structlog's contextvars for the life of one request."""

    async def dispatch(self, request: Request, call_next: RequestResponseEndpoint) -> Response:
        """Bind request context, log start/finish/failure, and stamp X-Request-ID on the response."""
        structlog.contextvars.clear_contextvars()
        request_id = str(uuid.uuid4())
        structlog.contextvars.bind_contextvars(request_id=request_id, method=request.method, path=request.url.path)

        start = time.perf_counter()
        logger.info("request_started")
        try:
            response = await call_next(request)
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            # Deliberately NOT `logger.exception()`: this middleware sits *inside* Starlette's
            # ServerErrorMiddleware, so an escaping exception is logged again -- with the full
            # traceback and blame frame -- by `handle_unhandled_exception`. Emitting the traceback
            # here too produced two stack dumps per failure, which doubles log volume and makes a
            # single failure look like two. This line's job is only to close the request lifecycle
            # (its duration), so it records the type and leaves the diagnosis to the handler.
            logger.warning("request_failed", duration_ms=duration_ms, exception_type=type(exc).__qualname__)
            raise

        duration_ms = (time.perf_counter() - start) * 1000
        logger.info("request_finished", status_code=response.status_code, duration_ms=duration_ms)
        response.headers["X-Request-ID"] = request_id
        return response
