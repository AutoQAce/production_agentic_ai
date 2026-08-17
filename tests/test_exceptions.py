"""Tests for the custom exception hierarchy + centralized handling.

Uses a throwaway test app (not app.main.app) wired with the same middleware/handlers, so we can
raise deliberate errors without adding debug routes to production code.
"""

from collections.abc import Iterator

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from app.core.exception_handlers import handle_app_exception, handle_unhandled_exception
from app.core.exceptions import AppException, ConfigurationError
from app.core.middleware import RequestContextMiddleware


def _all_subclasses(cls: type) -> Iterator[type]:
    """Every subclass, however deep — so this test picks up new AppException types automatically."""
    for sub in cls.__subclasses__():
        yield sub
        yield from _all_subclasses(sub)


@pytest.mark.parametrize("exc_cls", list(_all_subclasses(AppException)))
def test_every_app_exception_subclass_honors_the_base_contract(exc_cls: type[AppException]) -> None:
    """Catches what @abstractmethod can't: a subclass whose __init__ drops **context or skips
    super().__init__(), which abstractmethod-on-log_context() alone would not detect."""
    exc = exc_cls("test message", extra_field="value")

    assert isinstance(exc.error_code, str)
    assert isinstance(exc.http_status_code, int)
    assert exc.message == "test message"

    context = exc.log_context()
    assert context["error_code"] == exc.error_code
    assert context["extra_field"] == "value"

    # The leak-prevention guarantee itself: client_payload() must never carry context fields,
    # even though log_context() (checked above) is built from the same self.context.
    payload = exc.client_payload()
    assert payload == {"error": exc.error_code, "message": "test message"}
    assert "extra_field" not in payload


def _build_test_app() -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)
    test_app.add_exception_handler(AppException, handle_app_exception)
    test_app.add_exception_handler(Exception, handle_unhandled_exception)

    @test_app.get("/boom-classified")
    def boom_classified() -> None:
        raise ConfigurationError("bad config", field="LOG_LEVEL")

    @test_app.get("/boom-unclassified")
    def boom_unclassified() -> None:
        raise ValueError("surprise")

    return test_app


client = TestClient(_build_test_app(), raise_server_exceptions=False)


def test_classified_exception_is_logged_and_responds() -> None:
    with capture_logs() as logs:
        resp = client.get("/boom-classified")

    assert resp.status_code == 500
    assert resp.json() == {"error": "configuration_error", "message": "bad config"}

    app_exception_logs = [e for e in logs if e["event"] == "app_exception"]
    assert len(app_exception_logs) == 1
    assert app_exception_logs[0]["error_code"] == "configuration_error"
    assert app_exception_logs[0]["field"] == "LOG_LEVEL"


def test_unclassified_exception_is_logged_and_responds_generically() -> None:
    with capture_logs() as logs:
        resp = client.get("/boom-unclassified")

    assert resp.status_code == 500
    assert resp.json() == {"error": "internal_error", "message": "An unexpected error occurred."}

    unhandled_logs = [e for e in logs if e["event"] == "unhandled_exception"]
    assert len(unhandled_logs) == 1
