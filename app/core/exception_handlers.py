"""Where an exception becomes a structured log line + an HTTP response.

Logging and response-building are kept as separate functions, not two lines in one handler —
they're owned by different actors (observability/SRE owns the log shape; the API/product surface
owns the response contract) who can each independently demand a change here. The handler functions
FastAPI actually calls are pure wiring: sequence the two, nothing else. New failure types subclass
`AppException` (see `exceptions.py`); the handler dispatches generically off the base contract, so
adding a subclass never requires touching anything in this file (OCP).
"""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from app.core.exceptions import AppException
from app.core.logging import get_logger

logger = get_logger(__name__)


def _log_app_exception(exc: AppException) -> None:
    """Observability actor's line — isolated so a log-format change never risks touching
    what's actually returned to a client.
    """
    logger.error("app_exception", **exc.log_context())


def _respond_to_app_exception(exc: AppException) -> JSONResponse:
    """API/product actor's line — isolated so a response-contract change never risks touching
    how the error gets logged.
    """
    return JSONResponse(status_code=exc.http_status_code, content=exc.client_payload())


async def handle_app_exception(_request: Request, exc: AppException) -> JSONResponse:
    """FastAPI's registration point for AppException. Pure wiring — nobody has a business
    reason to change *this sequence*; it exists only to satisfy the handler calling convention.
    """
    _log_app_exception(exc)
    return _respond_to_app_exception(exc)


def _log_unhandled_exception() -> None:
    """Observability actor's line for anything not yet classified as an AppException."""
    logger.exception("unhandled_exception")


def _respond_to_unhandled_exception() -> JSONResponse:
    """API/product actor's line for anything not yet classified — always the same generic body."""
    return JSONResponse(
        status_code=500,
        content={"error": "internal_error", "message": "An unexpected error occurred."},
    )


async def handle_unhandled_exception(_request: Request, _exc: Exception) -> JSONResponse:
    """FastAPI's registration point for the catch-all — never let an error go unlogged."""
    _log_unhandled_exception()
    return _respond_to_unhandled_exception()
