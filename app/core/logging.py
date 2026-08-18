"""Structured logging pipeline, configured once at process start.

**One pipeline for the whole process.** Our own calls (via structlog) and every dependency's calls
(uvicorn, httpx, LangChain, via stdlib `logging`) are rendered by the same `ProcessorFormatter`, so
a production log stream has exactly one shape. Without that, uvicorn keeps its own handlers and the
stream comes out half JSON and half plain text -- the failure mode that makes a log aggregator
useless precisely when you need it.

**Output goes to stdout only, never to files.** Rotation, retention and shipping belong to the
platform (Docker log driver, systemd, the k8s node agent), which already does them correctly;
an in-process file handler re-implements them badly and adds a blocking disk write to the request
path.

Extension points, none of which require editing `configure_logging()` (OCP):

  * a new output format          -> one row in `_TAIL_PROCESSORS`
  * a new field on every line    -> one entry in `_shared_processors()`
  * a chatty dependency to tame  -> one row in `_MANAGED_LOGGERS`
  * a new redaction rule         -> `log_sanitizer.py` (separate owner; see that module)

The dependency is narrowed to the `LoggingConfig` Protocol rather than the concrete `Settings`
class, so the pipeline is configurable and testable without loading `.env` files (ISP + DIP).
"""

from __future__ import annotations

import logging
import sys
from typing import Protocol, runtime_checkable

import structlog

from app.core.exceptions import ConfigurationError
from app.core.log_sanitizer import sanitise_event_dict


@runtime_checkable
class LoggingConfig(Protocol):
    """The only settings this module needs.

    `Settings` satisfies it structurally -- no base class, no registration, and a test can pass a
    five-field stub instead of constructing real settings.
    """

    LOG_LEVEL: str
    LOG_FORMAT: str
    PROJECT_NAME: str
    VERSION: str
    APP_ENV: str


# Loggers whose handlers and verbosity this module takes over. `None` means "inherit the root
# level". Data, not branches: taming a newly chatty dependency is one row (OCP).
_MANAGED_LOGGERS: dict[str, int | None] = {
    "uvicorn": None,
    "uvicorn.error": None,
    # Suppressed rather than reformatted: `RequestContextMiddleware` already emits
    # request_started/request_finished carrying request_id, status and duration_ms, so uvicorn's
    # access line is a strictly poorer duplicate of a line we already pay to store.
    "uvicorn.access": logging.WARNING,
    # One INFO line per outbound HTTP call. An agent that loops over tool and LLM calls turns that
    # into the majority of its log volume, none of it actionable.
    "httpx": logging.WARNING,
    "httpcore": logging.WARNING,
}

# Cheap to add, expensive to render: each of these makes `CallsiteParameterAdder` walk the stack.
_CALLSITE_PARAMETERS = frozenset(
    {
        structlog.processors.CallsiteParameter.FILENAME,
        structlog.processors.CallsiteParameter.FUNC_NAME,
        structlog.processors.CallsiteParameter.LINENO,
    }
)

# Format -> the processors that turn a finished event dict into a line. A new format is one row.
_TAIL_PROCESSORS: dict[str, tuple[structlog.types.Processor, ...]] = {
    # `dict_tracebacks` renders `exception` as a list of structured frames (`exc_type`, `exc_value`,
    # `frames`, ...) so an aggregator can index and alert on exception type or raising function.
    # `format_exc_info` would put the same information in as one flat `str` -- greppable at best.
    "json": (structlog.processors.dict_tracebacks, structlog.processors.JSONRenderer()),
    # No exception processor here: ConsoleRenderer renders raw exc_info itself, and doing it here
    # keeps the door open for `rich` (which it uses when installed) to produce a source-annotated
    # traceback. Measured with rich absent, this is byte-identical to pre-formatting via
    # `format_exc_info` -- so the gain is conditional, but there is no case where it is worse.
    "console": (structlog.dev.ConsoleRenderer(),),
}


def _tail_processors_for(log_format: str) -> tuple[structlog.types.Processor, ...]:
    """Look up the rendering chain for a LOG_FORMAT value; unknown values fail loud, not silently."""
    try:
        return _TAIL_PROCESSORS[log_format]
    except KeyError as exc:
        raise ConfigurationError(
            f"Unknown LOG_FORMAT: {log_format!r}", valid_formats=sorted(_TAIL_PROCESSORS)
        ) from exc


def _wants_callsite(config: LoggingConfig) -> bool:
    """Whether to pay for file/function/line on every line.

    `CallsiteParameterAdder` walks the stack per event. Measured on this chain it costs ~30 us of a
    ~74 us log line -- about 41% overhead -- and in an agentic system log volume scales with tool
    calls and streamed steps, not with requests. So it is on where a human is reading the output
    (console) or has explicitly asked for detail (DEBUG), and off otherwise, where `logger` +
    `event` already say where a line came from and any error carries a full structured traceback.
    """
    return config.LOG_FORMAT == "console" or config.LOG_LEVEL == "DEBUG"


def _service_fields(config: LoggingConfig) -> structlog.types.Processor:
    """Stamp service identity on every line.

    Built once and closed over, so the config is read at configuration time rather than per event.
    Without these three fields a shared aggregator cannot tell which service, release or
    environment a line came from -- which is most of what you ask it during an incident.
    """
    fields = {"service": config.PROJECT_NAME, "version": config.VERSION, "env": config.APP_ENV}

    def add_service_fields(
        _logger: object, _method_name: str, event_dict: structlog.types.EventDict
    ) -> structlog.types.EventDict:
        # Service fields first, then the event's own -- a call site that binds `env=` deliberately
        # still wins, and the stable fields lead the rendered line.
        return {**fields, **event_dict}

    return add_service_fields


def _shared_processors(config: LoggingConfig, *, include_callsite: bool) -> list[structlog.types.Processor]:
    """Processors applied to every line, whether it originates from structlog or stdlib logging."""
    processors: list[structlog.types.Processor] = [
        # Request-scoped context (request_id, and later user_id/session_id/trace_id) bound by
        # middleware. structlog's own contextvars, not a hand-rolled ContextVar: this one is
        # already async- and task-safe and is what `bind_contextvars` writes to.
        structlog.contextvars.merge_contextvars,
        _service_fields(config),
        structlog.stdlib.add_logger_name,
        structlog.stdlib.add_log_level,
        # Foreign libraries log `"took %d ms", 12` -- without this the args never reach the output.
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]
    if include_callsite:
        processors.append(structlog.processors.CallsiteParameterAdder(_CALLSITE_PARAMETERS))
    # Last, deliberately: every field added above -- including anything a dependency contributed
    # via `extra=` -- passes through redaction and size capping before it can reach a renderer.
    processors.append(sanitise_event_dict)
    return processors


def configure_logging(config: LoggingConfig) -> None:
    """Configure structlog + stdlib logging for the whole process. Idempotent; call once at start."""
    tail = _tail_processors_for(config.LOG_FORMAT)
    shared = _shared_processors(config, include_callsite=_wants_callsite(config))

    structlog.configure(
        processors=[
            # First, so a suppressed line costs one `isEnabledFor()` call instead of the whole
            # chain. At DEBUG-heavy call sites in an agent loop that is the difference between a
            # free log statement and a measurable one.
            structlog.stdlib.filter_by_level,
            *shared,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        # False because caching freezes a logger's processor list on first use, and a later
        # `configure_logging()` builds a *new* list -- so every already-used logger keeps rendering
        # with the old config. Verified: flip this to True and a re-configure is silently ignored
        # (a logger still stamps the previous PROJECT_NAME), which is exactly what the per-test
        # reconfiguration in tests/test_logging.py relies on.
        #
        # Note it does NOT break `structlog.testing.capture_logs()` -- that was true before
        # structlog 25.5, which now mutates the configured list in place specifically "to not break
        # references held by bound loggers" (structlog/testing.py). Measured upside of caching is a
        # dict lookup on a ~74 us line. The costs worth attacking are elsewhere: `filter_by_level`
        # first (an 11.6x saving on a suppressed line) and no stack walking outside console/DEBUG.
        cache_logger_on_first_use=False,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        # `filter_by_level` is absent here on purpose: a foreign record has already passed stdlib's
        # level check, and this chain runs with `logger=None`, so the processor would raise.
        # `ExtraAdder` is first, so `logger.info(msg, extra={...})` from a dependency becomes real
        # fields -- and then gets sanitised by the tail of `shared` like everything else.
        foreign_pre_chain=[structlog.stdlib.ExtraAdder(), *shared],
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, *tail],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    for existing in root_logger.handlers:
        # Reconfiguration (tests, `uvicorn --reload`) must not leave orphaned handlers behind.
        # `StreamHandler.close()` detaches the handler without closing sys.stdout.
        existing.close()
    root_logger.handlers = [handler]
    root_logger.setLevel(config.LOG_LEVEL)

    _take_over_managed_loggers()

    # `warnings.warn()` -- including deprecation warnings from the LLM/agent stack -- becomes a
    # structured `py.warnings` line instead of unformatted text on stderr.
    logging.captureWarnings(True)

    get_logger(__name__).info(
        "logging_configured",
        log_level=config.LOG_LEVEL,
        log_format=config.LOG_FORMAT,
        callsite_info=_wants_callsite(config),
    )


def _take_over_managed_loggers() -> None:
    """Strip dependency loggers' own handlers so their lines route through our formatter.

    uvicorn applies its own `dictConfig` with `propagate=False` before it imports the app, so
    without this its lines never reach the root handler and are emitted unstructured.
    """
    for name, level in _MANAGED_LOGGERS.items():
        dependency_logger = logging.getLogger(name)
        for handler in dependency_logger.handlers:
            handler.close()
        dependency_logger.handlers = []
        dependency_logger.propagate = True
        # NOTSET, not "leave as-is": uvicorn pins these to INFO, which would otherwise override a
        # deliberate `LOG_LEVEL=WARNING` in production.
        dependency_logger.setLevel(logging.NOTSET if level is None else level)


def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to `name` -- the one call sites use (DIP)."""
    return structlog.get_logger(name)
