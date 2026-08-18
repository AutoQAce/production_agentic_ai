"""Where an exception becomes a structured log line + an HTTP response.

Two primitives, four handlers, one registry:

  * `_log_error()`      -- the observability actor's line. Owns *what gets logged*.
  * `_error_response()` -- the API actor's line. Owns *what the client sees*.
  * four thin handlers  -- one per exception family, each just sequencing the two.
  * `build_exception_handlers()` -- the registry `main.py` installs.

Logging and response-building are separate functions, not two lines in one handler, because they are
owned by different actors (observability/SRE owns the log shape; the API/product surface owns the
response contract) who can each independently demand a change. The handlers FastAPI actually calls
are pure wiring.

**Every error is logged with three layers of location information**, because each answers a different
question:

  * `raised_at`      -- where the `AppException` was constructed (from the exception itself)
  * `failed_at` + `blame` -- the deepest frame in **our** code (from the traceback)
  * `app_traceback`  -- the path the failure took through our layers, innermost first
  * plus `exc_info`, so the renderer attaches the complete formatted chain

The first three are small, flat and indexable -- you can facet a dashboard on `failed_at`. The fourth
is the full record you read once you have found the line. Logging only the traceback (the obvious
choice) gives you the fourth and none of the first three.

**Four handlers, not one, because four different things reach here** -- and two of them used to
escape entirely. `RequestValidationError` (422) and `StarletteHTTPException` (404/405) have default
FastAPI handlers registered *before* ours, so without explicit entries they answer with
`{"detail": ...}` while every other error answers with `{"error", "message", "error_id"}`. A client
cannot parse two shapes, so both are claimed here.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

import structlog
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.core.error_context import describe
from app.core.exceptions import AppException
from app.core.log_sanitizer import sanitise
from app.core.logging import get_logger

logger = get_logger(__name__)

# Status codes that mean "the caller made a mistake". They are logged at WARNING, not ERROR: a 404 is
# not a defect in this service, and paging on them trains people to ignore the alert.
_CLIENT_ERROR_CEILING = 500


@runtime_checkable
class ErrorDetailConfig(Protocol):
    """The only setting these handlers need: whether to put diagnostics in the response body.

    A one-field Protocol rather than `Settings`, for the same reason as `LoggingConfig` -- a test
    passes a stub and never touches `.env`. `Settings` satisfies it structurally.
    """

    DEBUG: bool


def _request_id() -> str | None:
    """The current request's id, as bound by `RequestContextMiddleware`.

    Read from structlog's contextvars rather than passed in, because the handler signature is fixed
    by FastAPI. Returning it to the client is what lets a user's screenshot be traced to a log line.
    """
    value = structlog.contextvars.get_contextvars().get("request_id")
    return str(value) if value is not None else None


def _log_error(event: str, exc: BaseException, *, level: str, **extra: Any) -> None:
    """The observability actor's line -- isolated so a log-format change never risks touching
    what is actually returned to a client.

    `exc_info=exc` is passed explicitly rather than relying on `logger.exception()`, because these
    handlers are `async` and the exception is an argument: there is no guarantee we are still inside
    the `except` block that `sys.exc_info()` would read from.
    """
    getattr(logger, level)(event, exc_info=exc, **describe(exc), **extra)


def _error_response(
    *,
    status_code: int,
    error_code: str,
    message: str,
    error_id: str | None = None,
    debug: dict[str, Any] | None = None,
    extra: dict[str, Any] | None = None,
) -> JSONResponse:
    """The API actor's line -- isolated so a response-contract change never risks touching how the
    error gets logged.

    One envelope for every error path in the app: `error` (a stable machine-readable code), `message`
    (human-readable), `error_id` (the log correlation token) and `request_id`. `debug` is present
    only when the caller passes it, which only happens under DEBUG.
    """
    body: dict[str, Any] = {"error": error_code, "message": message}
    if error_id is not None:
        body["error_id"] = error_id
    request_id = _request_id()
    if request_id is not None:
        body["request_id"] = request_id
    if extra:
        body.update(extra)
    if debug is not None:
        # Sanitised, not passed through. A DEBUG response body is a second sink for the same
        # exception context that the log pipeline redacts, and it is the *more* exposed of the two:
        # developers paste HTTP responses into tickets and chat. Without this, an `AppException`
        # carrying `api_key=...` for debugging would render the live key verbatim in the response.
        body["debug"] = sanitise(debug)
    return JSONResponse(status_code=status_code, content=body)


def build_exception_handlers(
    config: ErrorDetailConfig,
) -> dict[type[Exception], Any]:
    """Build the exception-handler registry for `main.py` to install.

    A factory closing over `config` rather than four module-level functions reading a global: the
    DEBUG decision is made once, here, and each handler receives it as a captured value (DIP). It is
    also what makes "does this leak internals in production?" a single testable question rather than
    four.

    Returns a mapping, so registering is a loop in `main.py` and adding a handler is **one row** --
    `configure`-style wiring stays out of the app factory (OCP).
    """
    debug = config.DEBUG

    async def handle_app_exception(_request: Request, exc: AppException) -> JSONResponse:
        """Our own classified failures -- the only path that already knows its own error code.

        `exc` is annotated with the concrete type rather than `Exception` + an `isinstance` assert:
        the registry below guarantees Starlette only routes `AppException` here, and an `assert`
        would be compiled out under `python -O` anyway.
        """
        # Client errors are the caller's fault and must not read as service defects; 5xx must.
        level = "warning" if exc.http_status_code < _CLIENT_ERROR_CEILING else "error"
        _log_error("app_exception", exc, level=level, **exc.log_context())
        return _error_response(
            status_code=exc.http_status_code,
            error_code=exc.error_code,
            message=exc.message,
            error_id=exc.error_id,
            debug=exc.debug_payload() if debug else None,
        )

    async def handle_validation_error(_request: Request, exc: RequestValidationError) -> JSONResponse:
        """Request-shape failures (422).

        Claimed from FastAPI's default handler so the envelope stays consistent. `errors` *is*
        forwarded to the client -- unlike other context, "which field was wrong" is the entire point
        of a 422, and it describes the caller's own request rather than our internals.
        """
        errors = [
            {
                "field": ".".join(str(part) for part in error.get("loc", ())),
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            }
            for error in exc.errors()
        ]
        _log_error("request_validation_failed", exc, level="warning", validation_errors=errors)
        return _error_response(
            status_code=422,
            error_code="validation_error",
            message="Request validation failed.",
            extra={"errors": errors},
        )

    async def handle_http_exception(_request: Request, exc: StarletteHTTPException) -> JSONResponse:
        """Starlette's own `HTTPException` -- 404s, 405s, and anything raised as `HTTPException`.

        Also claimed from FastAPI's default so a missing route answers in the same shape as a failed
        LLM call. Logged at WARNING for 4xx: a 404 is routine traffic, not an incident.
        """
        level = "warning" if exc.status_code < _CLIENT_ERROR_CEILING else "error"
        _log_error("http_exception", exc, level=level, status_code=exc.status_code)
        return _error_response(
            status_code=exc.status_code,
            error_code=f"http_{exc.status_code}",
            message=str(exc.detail),
        )

    async def handle_unhandled_exception(_request: Request, exc: Exception) -> JSONResponse:
        """The catch-all: anything not yet classified as an `AppException`.

        The response body is deliberately generic and carries no detail outside DEBUG -- an
        unclassified exception's message is the one most likely to contain a connection string, a
        row of data, or a provider's raw error text. The log line carries everything.
        """
        _log_error("unhandled_exception", exc, level="error")
        return _error_response(
            status_code=500,
            error_code="internal_error",
            message="An unexpected error occurred.",
            debug=describe(exc) if debug else None,
        )

    # The registry. Order is irrelevant -- Starlette dispatches on the most specific class in the
    # exception's MRO, not on insertion order.
    return {
        AppException: handle_app_exception,
        RequestValidationError: handle_validation_error,
        StarletteHTTPException: handle_http_exception,
        Exception: handle_unhandled_exception,
    }
