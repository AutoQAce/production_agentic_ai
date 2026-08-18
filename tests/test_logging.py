"""Tests for the logging pipeline: rendering, redaction, level filtering, and request lifecycle.

Most tests here drive the *real* pipeline and parse the JSON that lands on stdout, rather than
using `capture_logs()`. `capture_logs()` short-circuits the processor chain, so it can only prove
what a call site passed -- not that redaction, service fields or the renderer actually ran.
"""

import json
import logging
from dataclasses import dataclass

import pytest
import structlog
from fastapi.testclient import TestClient
from pydantic import SecretStr
from structlog.testing import capture_logs

from app.core.config import get_settings
from app.core.exceptions import ConfigurationError
from app.core.log_sanitizer import REDACTED, sanitise_event_dict
from app.core.logging import configure_logging, get_logger
from app.main import app

client = TestClient(app)


@dataclass
class FakeConfig:
    """Minimal stand-in satisfying the LoggingConfig Protocol -- no .env files involved."""

    LOG_LEVEL: str = "INFO"
    LOG_FORMAT: str = "json"
    PROJECT_NAME: str = "test-service"
    VERSION: str = "9.9.9"
    APP_ENV: str = "test"


@pytest.fixture(autouse=True)
def _restore_real_logging():
    """Tests below reconfigure global logging; put the app's own configuration back afterwards."""
    yield
    configure_logging(get_settings())


def emitted_lines(capsys) -> list[dict]:
    """Parsed JSON log lines written to stdout, ignoring the `logging_configured` startup line."""
    captured = capsys.readouterr().out.strip().splitlines()
    events = [json.loads(line) for line in captured if line.startswith("{")]
    return [event for event in events if event["event"] != "logging_configured"]


# --------------------------------------------------------------------------------------
# Pipeline output
# --------------------------------------------------------------------------------------


def test_json_line_carries_service_identity_and_standard_fields(capsys) -> None:
    # configure_logging must run *inside* the test: the StreamHandler binds to sys.stdout at
    # construction, and capsys has already replaced it by now.
    configure_logging(FakeConfig())
    get_logger("app.some.module").info("thing_happened", customer_count=3)

    (event,) = emitted_lines(capsys)
    assert event["event"] == "thing_happened"
    assert event["level"] == "info"
    assert event["logger"] == "app.some.module"
    assert event["service"] == "test-service"
    assert event["version"] == "9.9.9"
    assert event["env"] == "test"
    assert event["customer_count"] == 3
    assert event["timestamp"].endswith("Z")


def test_callsite_info_is_omitted_in_json_but_present_at_debug(capsys) -> None:
    configure_logging(FakeConfig(LOG_LEVEL="INFO", LOG_FORMAT="json"))
    get_logger("x").info("no_callsite")
    assert "lineno" not in emitted_lines(capsys)[0]

    configure_logging(FakeConfig(LOG_LEVEL="DEBUG", LOG_FORMAT="json"))
    get_logger("x").info("with_callsite")
    event = emitted_lines(capsys)[0]
    assert event["lineno"] > 0
    assert event["func_name"] == "test_callsite_info_is_omitted_in_json_but_present_at_debug"


def test_level_filtering_drops_lines_below_configured_level(capsys) -> None:
    configure_logging(FakeConfig(LOG_LEVEL="WARNING"))
    log = get_logger("x")
    log.info("dropped")
    log.warning("kept")

    assert [event["event"] for event in emitted_lines(capsys)] == ["kept"]


def test_exception_is_rendered_as_a_structured_traceback(capsys) -> None:
    configure_logging(FakeConfig())
    try:
        raise ValueError("boom")
    except ValueError:
        get_logger("x").exception("it_broke")

    (event,) = emitted_lines(capsys)
    assert event["level"] == "error"
    # dict_tracebacks -> a list of frames, not one opaque string, so an aggregator can index on it.
    assert isinstance(event["exception"], list)
    assert event["exception"][-1]["exc_type"] == "ValueError"
    assert event["exception"][-1]["exc_value"] == "boom"


def test_foreign_stdlib_logger_is_rendered_through_the_same_pipeline(capsys) -> None:
    configure_logging(FakeConfig())
    logging.getLogger("some.third_party").warning("legacy %s line", "formatted", extra={"attempt": 2})

    (event,) = emitted_lines(capsys)
    assert event["event"] == "legacy formatted line"
    assert event["logger"] == "some.third_party"
    assert event["level"] == "warning"
    assert event["service"] == "test-service"
    assert event["attempt"] == 2  # ExtraAdder promoted `extra=` into real fields


def test_managed_dependency_loggers_are_taken_over(capsys) -> None:
    noisy = logging.getLogger("httpx")
    noisy.addHandler(logging.NullHandler())
    noisy.propagate = False

    configure_logging(FakeConfig())

    assert noisy.handlers == []
    assert noisy.propagate is True
    assert noisy.level == logging.WARNING
    # uvicorn's access line duplicates our own request_finished, so it is suppressed.
    assert logging.getLogger("uvicorn.access").level == logging.WARNING
    # ...while uvicorn.error inherits the root level rather than uvicorn's pinned INFO.
    assert logging.getLogger("uvicorn.error").level == logging.NOTSET


def test_unknown_log_format_fails_loudly() -> None:
    with pytest.raises(ConfigurationError):
        configure_logging(FakeConfig(LOG_FORMAT="yaml"))


def test_console_format_renders_without_json(capsys) -> None:
    configure_logging(FakeConfig(LOG_FORMAT="console"))
    get_logger("x").info("pretty")

    out = capsys.readouterr().out
    assert "pretty" in out
    assert not out.strip().startswith("{")


# --------------------------------------------------------------------------------------
# Redaction and size capping (log_sanitizer)
# --------------------------------------------------------------------------------------


def test_credentials_are_redacted_end_to_end(capsys) -> None:
    configure_logging(FakeConfig())
    get_logger("x").info(
        "llm_call",
        api_key="sk-live-123",
        headers={"Authorization": "Bearer abc", "X-Request-Id": "keep-me"},
        db_password="hunter2",
        prompt_tokens=812,
    )

    (event,) = emitted_lines(capsys)
    assert event["api_key"] == REDACTED
    assert event["db_password"] == REDACTED
    assert event["headers"]["Authorization"] == REDACTED
    assert event["headers"]["X-Request-Id"] == "keep-me"
    # The metric an agentic system exists to watch must survive a deny-list built around "token".
    assert event["prompt_tokens"] == 812


@pytest.mark.parametrize(
    "key",
    ["password", "API-Key", "openai_api_key", "jwt", "token", "set_cookie", "client_secret", "user_credentials"],
)
def test_sensitive_key_variants_are_redacted(key: str) -> None:
    assert sanitise_event_dict(None, "info", {key: "value"})[key] == REDACTED


@pytest.mark.parametrize("key", ["prompt_tokens", "total_tokens", "token_budget", "session_id", "request_id"])
def test_correlation_ids_and_token_metrics_survive(key: str) -> None:
    assert sanitise_event_dict(None, "info", {key: 42})[key] == 42


def test_secretstr_is_redacted_regardless_of_key_name() -> None:
    result = sanitise_event_dict(None, "info", {"harmless_name": SecretStr("s3kr1t")})
    assert result["harmless_name"] == REDACTED


def test_oversized_string_is_capped_with_the_original_length() -> None:
    completion = "x" * 5_000
    result = sanitise_event_dict(None, "info", {"completion": completion})

    assert len(result["completion"]) < len(completion)
    assert result["completion"].endswith("[truncated, 5000 chars total]")


def test_oversized_collection_is_capped() -> None:
    result = sanitise_event_dict(None, "info", {"chunks": list(range(500))})

    assert len(result["chunks"]) == 51
    assert result["chunks"][-1] == "...[truncated, 500 items total]"


def test_deeply_nested_payload_is_elided_rather_than_walked_forever() -> None:
    payload: dict = {"leaf": "bottom"}
    for _ in range(20):
        payload = {"nested": payload}

    rendered = json.dumps(sanitise_event_dict(None, "info", payload))
    assert "elided at depth" in rendered
    assert "bottom" not in rendered


def test_bytes_values_are_decoded_and_capped() -> None:
    result = sanitise_event_dict(None, "info", {"blob": b"raw \xff bytes"})
    assert result["blob"].startswith("raw ")

    big = sanitise_event_dict(None, "info", {"blob": b"y" * 5_000})
    assert big["blob"].endswith("[truncated, 5000 chars total]")


def test_deeply_nested_collection_is_elided() -> None:
    payload: list = ["bottom"]
    for _ in range(20):
        payload = [payload]

    rendered = json.dumps(sanitise_event_dict(None, "info", {"chunks": payload}))
    assert "elided at depth" in rendered
    assert "bottom" not in rendered


def test_internal_and_live_objects_pass_through_untouched() -> None:
    exc_info = (ValueError, ValueError("x"), None)
    result = sanitise_event_dict(None, "info", {"exc_info": exc_info, "_record": object()})
    assert result["exc_info"] is exc_info


def test_sanitiser_does_not_mutate_the_callers_dict() -> None:
    original = {"password": "hunter2", "nested": {"api_key": "sk-1"}}
    sanitise_event_dict(None, "info", original)

    assert original["password"] == "hunter2"
    assert original["nested"]["api_key"] == "sk-1"


# --------------------------------------------------------------------------------------
# Request lifecycle
# --------------------------------------------------------------------------------------


def test_health_request_emits_lifecycle_logs_with_request_id() -> None:
    # capture_logs() disables ALL configured processors by default (structlog >= 25.5), so
    # merge_contextvars must be passed explicitly or request_id/method/path never reach the
    # captured event dicts even though they're correctly bound at runtime.
    with capture_logs(processors=[structlog.contextvars.merge_contextvars]) as logs:
        resp = client.get("/health")

    assert resp.status_code == 200
    assert "X-Request-ID" in resp.headers

    events = {entry["event"] for entry in logs}
    assert "request_started" in events
    assert "request_finished" in events
    assert "health_check_invoked" in events

    finished = next(e for e in logs if e["event"] == "request_finished")
    assert finished["status_code"] == 200
    assert finished["request_id"] == resp.headers["X-Request-ID"]
    assert finished["method"] == "GET"
    assert finished["path"] == "/health"
