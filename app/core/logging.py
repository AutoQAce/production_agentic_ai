"""Structured logging configuration — Bible Step 7 (Observability), built ahead of the numbered
sequence per Appendix C, because config-loading itself needs to be traceable from the start.

Wires structlog and stdlib logging into one pipeline so every log line (ours and uvicorn's) shares
the same processors, renderer, and level. New renderers register in `_RENDERERS`; new processors
append to `_shared_processors()` — neither requires touching `configure_logging()` itself (OCP).
No GenAI/OpenTelemetry-specific fields yet — those slot into `_shared_processors()` later, once
there's LLM/agent code to produce them.
"""

from __future__ import annotations

import logging
import sys
from typing import Protocol, runtime_checkable

import structlog

from app.core.exceptions import ConfigurationError


@runtime_checkable
class LoggingConfig(Protocol):
    """The only two fields `configure_logging()` needs.

    Narrowing the dependency to this instead of the full `Settings` class means logging can be
    configured and tested without loading `.env` files (ISP + DIP).
    """

    LOG_LEVEL: str
    LOG_FORMAT: str


def _shared_processors() -> list[structlog.types.Processor]:
    """Processors applied to every log line, whether it originates from structlog or stdlib logging."""
    return [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.CallsiteParameterAdder(
            {
                structlog.processors.CallsiteParameter.FILENAME,
                structlog.processors.CallsiteParameter.FUNC_NAME,
                structlog.processors.CallsiteParameter.LINENO,
            }
        ),
        structlog.processors.format_exc_info,
    ]


_RENDERERS: dict[str, structlog.types.Processor] = {
    "json": structlog.processors.JSONRenderer(),
    "console": structlog.dev.ConsoleRenderer(),
}


def _renderer_for(log_format: str) -> structlog.types.Processor:
    """Look up the renderer for a LOG_FORMAT value; unknown values fail loud, not silently."""
    try:
        return _RENDERERS[log_format]
    except KeyError as exc:
        raise ConfigurationError(f"Unknown LOG_FORMAT: {log_format!r}", valid_formats=sorted(_RENDERERS)) from exc


def configure_logging(config: LoggingConfig) -> None:
    """Configure structlog + stdlib logging once, at process start."""
    renderer = _renderer_for(config.LOG_FORMAT)
    shared = _shared_processors()

    structlog.configure(
        processors=[*shared, structlog.stdlib.ProcessorFormatter.wrap_for_formatter],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        # False, not True: caching resolves+locks each logger's processor chain on first use,
        # which breaks structlog.testing.capture_logs() across tests (a logger first touched
        # inside one test's capture block keeps writing there after the block closes). No
        # measured need for the cache at this project's scale.
        cache_logger_on_first_use=False,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared,
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, renderer],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers = [handler]
    root_logger.setLevel(config.LOG_LEVEL)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to `name` — the one call sites use (DIP)."""
    return structlog.get_logger(name)
