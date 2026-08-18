"""Benchmark the logging pipeline. Reproduces every figure in docs/4_logging_guide.md.

    PYTHONPATH=. uv run python scripts/bench_logging.py

Figures are single-machine and vary run to run; what the guide's arguments rest on is the
*ordering* and the ratios, which are stable.
"""

from __future__ import annotations

import io
import logging
import timeit

import structlog

from app.core.log_sanitizer import sanitise_event_dict
from app.core.logging import configure_logging

EVENT = {
    "model": "gpt-5.4-mini",
    "prompt_tokens": 812,
    "completion_tokens": 240,
    "duration_ms": 1432.5,
    "request_id": "b3f1c2d4-1111-2222-3333-444455556666",
    "tool": "search_filings",
}
NESTED = dict(EVENT, messages=[{"role": "user", "content": "x" * 400} for _ in range(8)])

CALLSITE = structlog.processors.CallsiteParameterAdder(
    {
        structlog.processors.CallsiteParameter.FILENAME,
        structlog.processors.CallsiteParameter.FUNC_NAME,
        structlog.processors.CallsiteParameter.LINENO,
    }
)


class Cfg:
    """Stand-in satisfying the LoggingConfig Protocol."""

    LOG_LEVEL = "INFO"
    LOG_FORMAT = "json"
    PROJECT_NAME = "bench"
    VERSION = "0"
    APP_ENV = "test"


def _cfg(**over: object) -> object:
    return type("C", (Cfg,), over)()


def _us(fn: object, number: int = 20_000) -> float:
    fn()  # type: ignore[operator]
    return timeit.timeit(fn, number=number) / number * 1e6  # type: ignore[arg-type]


def _sink() -> io.StringIO:
    """Point the root handler at a buffer without touching its formatter."""
    buf = io.StringIO()
    logging.getLogger().handlers[0].stream = buf  # type: ignore[attr-defined]
    return buf


def per_processor() -> None:
    print("=" * 72)
    print("Per-processor cost (event dict with 7 fields)")
    print("=" * 72)
    candidates = {
        "sanitise_event_dict": lambda: sanitise_event_dict(None, "info", dict(EVENT)),
        "JSONRenderer": lambda: structlog.processors.JSONRenderer()(None, "info", dict(EVENT)),
        "CallsiteParameterAdder": lambda: CALLSITE(None, "info", dict(EVENT)),
        "TimeStamper(iso, utc)": lambda: structlog.processors.TimeStamper(fmt="iso", utc=True)(
            None, "info", dict(EVENT)
        ),
        "UnicodeDecoder": lambda: structlog.processors.UnicodeDecoder()(None, "info", dict(EVENT)),
        "StackInfoRenderer": lambda: structlog.processors.StackInfoRenderer()(None, "info", dict(EVENT)),
        "merge_contextvars": lambda: structlog.contextvars.merge_contextvars(None, "info", dict(EVENT)),
        "add_log_level": lambda: structlog.stdlib.add_log_level(None, "info", dict(EVENT)),
    }
    results = {name: _us(fn) for name, fn in candidates.items()}
    for name, cost in sorted(results.items(), key=lambda kv: -kv[1]):
        print(f"  {name:24} {cost:7.2f} us")
    print(f"  -> most expensive: {max(results, key=lambda k: results[k])}")

    print("\n  nested agent payload (8 messages x 400 chars):")
    print(
        f"    {'sanitise_event_dict':22} {_us(lambda: sanitise_event_dict(None, 'info', dict(NESTED)), 5000):7.2f} us"
    )
    print(f"    {'CallsiteParameterAdder':22} {_us(lambda: CALLSITE(None, 'info', dict(NESTED)), 5000):7.2f} us")


def whole_line() -> None:
    print()
    print("=" * 72)
    print("One full log line: callsite OFF (production) vs ON (DEBUG/console)")
    print("=" * 72)
    costs = {}
    for level, label in (("INFO", "production default, callsite OFF"), ("DEBUG", "callsite ON")):
        configure_logging(_cfg(LOG_LEVEL=level))  # type: ignore[arg-type]
        _sink()
        log = structlog.get_logger("bench")
        costs[level] = _us(lambda bound=log: bound.info("llm_call_finished", **EVENT), 5000)
        print(f"  LOG_LEVEL={level:6} {costs[level]:7.2f} us/line  ({label})")
    delta = costs["DEBUG"] - costs["INFO"]
    print(f"  -> callsite adds {delta:.2f} us/line ({(costs['DEBUG'] / costs['INFO'] - 1) * 100:.0f}% overhead)")
    print(f"  -> throughput at production settings: {1e6 / costs['INFO']:,.0f} lines/sec on one core")


def suppressed() -> None:
    print()
    print("=" * 72)
    print("Suppressed vs emitted (filter_by_level first)")
    print("=" * 72)
    configure_logging(_cfg(LOG_LEVEL="WARNING"))  # type: ignore[arg-type]
    _sink()
    log = structlog.get_logger("bench")
    dropped = _us(lambda: log.info("never_emitted", **EVENT))
    emitted = _us(lambda: log.warning("emitted", **EVENT))
    print(f"  suppressed INFO line   {dropped:7.2f} us")
    print(f"  emitted   WARNING line {emitted:7.2f} us")
    print(f"  -> {emitted / dropped:.1f}x cheaper to suppress")


def sanitizer_share() -> None:
    print()
    print("=" * 72)
    print("Sanitizer share of one emitted line (the price of the security guarantee)")
    print("=" * 72)
    configure_logging(_cfg())  # type: ignore[arg-type]
    _sink()
    log = structlog.get_logger("bench")
    for label, payload in (("flat payload", EVENT), ("nested agent payload", NESTED)):
        total = _us(lambda p=payload: log.info("llm_call_finished", **p), 3000)
        san = _us(lambda p=payload: sanitise_event_dict(None, "info", dict(p)), 3000)
        print(f"  {label:22} total {total:7.2f} us | sanitizer {san:6.2f} us ({san / total * 100:4.1f}%)")


if __name__ == "__main__":
    per_processor()
    whole_line()
    suppressed()
    sanitizer_share()
