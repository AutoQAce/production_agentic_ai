"""Tests for the exception hierarchy, stack introspection, and centralized handling.

Uses a throwaway test app (not app.main.app) wired with the same middleware/handlers, so we can
raise deliberate errors without adding debug routes to production code.
"""

from collections.abc import Iterator
from dataclasses import dataclass

import pytest
import structlog
from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from app.core.error_context import (
    _MAX_FIRST_PARTY_FRAMES,
    CodeOrigin,
    _classify,
    _display_path,
    blame_frame,
    capture_origin,
    describe,
    first_party_frames,
    is_first_party,
)
from app.core.exception_handlers import build_exception_handlers
from app.core.exceptions import AppException, ConfigurationError
from app.core.middleware import RequestContextMiddleware


@dataclass
class FakeConfig:
    """Minimal stand-in satisfying the ErrorDetailConfig Protocol."""

    DEBUG: bool = False


def _all_subclasses(cls: type) -> Iterator[type]:
    """Every subclass, however deep — so this test picks up new AppException types automatically."""
    for sub in cls.__subclasses__():
        yield sub
        yield from _all_subclasses(sub)


# --------------------------------------------------------------------------------------
# The base contract
# --------------------------------------------------------------------------------------


@pytest.mark.parametrize("exc_cls", list(_all_subclasses(AppException)))
def test_every_app_exception_subclass_honors_the_base_contract(exc_cls: type[AppException]) -> None:
    """Catches what @abstractmethod can't: a subclass whose __init__ drops **context or skips
    super().__init__(), which abstractmethod-on-log_context() alone would not detect."""
    exc = exc_cls("test message", extra_field="value")

    assert isinstance(exc.error_code, str)
    assert isinstance(exc.http_status_code, int)
    assert exc.message == "test message"
    assert len(exc.error_id) == 12

    context = exc.log_context()
    assert context["error_code"] == exc.error_code
    assert context["extra_field"] == "value"
    assert context["error_id"] == exc.error_id

    # The leak-prevention guarantee itself: client_payload() must never carry context fields,
    # even though log_context() (checked above) is built from the same self.context.
    payload = exc.client_payload()
    assert payload == {"error": exc.error_code, "message": "test message", "error_id": exc.error_id}
    assert "extra_field" not in payload
    assert "raised_at" not in payload


def test_exception_records_the_line_that_raised_it() -> None:
    exc = ConfigurationError("bad config", field="LOG_LEVEL")

    assert exc.origin is not None
    assert exc.origin.file == "tests/test_exceptions.py"
    assert exc.origin.function == "test_exception_records_the_line_that_raised_it"
    assert exc.origin.first_party is True
    assert exc.log_context()["raised_at"].startswith("tests/test_exceptions.py:")


def test_subclass_with_its_own_init_still_records_the_callers_line() -> None:
    """The reason `capture_origin` skips by *file* instead of counting stack levels: an extra
    __init__ in the hierarchy would shift a hardcoded stacklevel and blame exceptions.py."""

    class LayeredError(ConfigurationError):
        def __init__(self, message: str, **context: object) -> None:
            super().__init__(message, **context)

    exc = LayeredError("deep")

    assert exc.origin is not None
    assert exc.origin.file == "tests/test_exceptions.py"
    assert exc.origin.function == "test_subclass_with_its_own_init_still_records_the_callers_line"


def test_hint_reaches_logs_and_debug_but_never_the_client() -> None:
    exc = ConfigurationError("bad", hint="add it to ENVIRONMENT_TIERS")

    assert exc.log_context()["hint"] == "add it to ENVIRONMENT_TIERS"
    assert exc.debug_payload()["hint"] == "add it to ENVIRONMENT_TIERS"
    assert "hint" not in exc.client_payload()


def test_error_ids_are_unique_per_instance() -> None:
    ids = {ConfigurationError("x").error_id for _ in range(100)}
    assert len(ids) == 100


# --------------------------------------------------------------------------------------
# Stack introspection (error_context)
# --------------------------------------------------------------------------------------


def test_is_first_party_separates_our_code_from_dependencies() -> None:
    assert is_first_party(__file__) is True
    assert is_first_party(structlog.__file__) is False  # lives in .venv


@pytest.mark.parametrize("filename", ["<string>", "<frozen importlib._bootstrap>", "", "bad\0path"])
def test_non_paths_are_never_first_party(filename: str) -> None:
    """`Path("<string>").resolve()` anchors to the CWD — which is this project root — so without an
    explicit guard every synthetic frame would be misreported as our own code."""
    assert is_first_party(filename) is False
    # _display_path must survive them too: a diagnostic helper may never raise.
    assert isinstance(_display_path(filename), str)


def test_display_path_shortens_dependency_paths() -> None:
    assert _display_path(structlog.__file__) == "structlog/__init__.py"
    assert _display_path(__file__) == "tests/test_exceptions.py"


def test_capture_origin_reports_the_calling_function() -> None:
    origin = capture_origin()

    assert origin is not None
    assert origin.function == "test_capture_origin_reports_the_calling_function"
    assert origin.file == "tests/test_exceptions.py"


def test_capture_origin_reports_the_class_not_just_the_method() -> None:
    """`co_qualname` is what makes the class visible — `co_name` alone would say only 'run'."""

    class Worker:
        def run(self) -> CodeOrigin | None:
            return capture_origin()

    origin = Worker().run()

    assert origin is not None
    assert origin.function.endswith("Worker.run")


def _innermost_failure() -> None:
    raise ValueError("the real cause")


def _middle_layer() -> None:
    _innermost_failure()


def _outer_layer() -> None:
    _middle_layer()


def test_blame_frame_points_at_the_deepest_line_of_our_own_code() -> None:
    with pytest.raises(ValueError) as excinfo:
        _outer_layer()
    blame = blame_frame(excinfo.value)
    frames = first_party_frames(excinfo.value)

    assert blame is not None
    assert blame.function == "_innermost_failure"
    assert blame.file == "tests/test_exceptions.py"

    # Innermost first: the line that broke, then each caller that led there.
    assert [f.function for f in frames[:4]] == [
        "_innermost_failure",
        "_middle_layer",
        "_outer_layer",
        "test_blame_frame_points_at_the_deepest_line_of_our_own_code",
    ]


def test_blame_frame_skips_dependency_frames() -> None:
    """The whole point: a failure raised inside a library must still blame *our* calling line."""
    import json

    with pytest.raises(ValueError) as excinfo:
        json.loads("{not json}")
    blame = blame_frame(excinfo.value)

    assert blame is not None
    # json/decoder.py raised it; our line is the one worth reading.
    assert blame.file == "tests/test_exceptions.py"
    assert blame.function == "test_blame_frame_skips_dependency_frames"


def _wrap_innermost_failure() -> None:
    try:
        _innermost_failure()
    except ValueError as root:
        raise ConfigurationError("wrapped") from root


def test_describe_reports_the_cause_chain() -> None:
    with pytest.raises(ConfigurationError) as excinfo:
        _wrap_innermost_failure()
    described = describe(excinfo.value)

    assert described["exception_type"] == "ConfigurationError"
    assert described["failed_at"].startswith("tests/test_exceptions.py:")
    assert described["caused_by"] == ["ValueError: the real cause"]
    assert any("_innermost_failure" in location for location in described["app_traceback"])


def _recurse(depth: int) -> None:
    if depth == 0:
        raise ValueError("bottom")
    _recurse(depth - 1)


def test_first_party_frames_are_capped() -> None:
    """Runaway recursion must not produce a log line thousands of frames long."""
    with pytest.raises(ValueError) as excinfo:
        _recurse(60)

    frames = first_party_frames(excinfo.value)
    assert len(frames) == _MAX_FIRST_PARTY_FRAMES
    # The cap keeps the *innermost* frames — the ones nearest the failure.
    assert frames[0].function == "_recurse"


def test_path_classification_is_cached() -> None:
    """The cache is load-bearing, not an optimisation: `Path.resolve()` is a filesystem syscall, and
    without it `describe()` cost 40 ms on a 22-frame traceback (measured) because every frame of
    every walk paid for it. Errors arrive in bursts, so that lands when you can least afford it."""
    _classify.cache_clear()
    _classify(__file__)
    for _ in range(50):
        _classify(__file__)

    info = _classify.cache_info()
    assert info.misses == 1
    assert info.hits == 50


def test_describe_survives_an_exception_with_no_traceback() -> None:
    described = describe(ValueError("never raised"))

    assert described["exception_type"] == "ValueError"
    assert "blame" not in described


def _suppress_innermost_failure() -> None:
    try:
        _innermost_failure()
    except ValueError:
        raise ConfigurationError("standalone") from None


def test_suppressed_context_is_honoured() -> None:
    """`raise X from None` is an explicit statement that the earlier error is irrelevant."""
    with pytest.raises(ConfigurationError) as excinfo:
        _suppress_innermost_failure()

    assert "caused_by" not in describe(excinfo.value)


# --------------------------------------------------------------------------------------
# End-to-end handling
# --------------------------------------------------------------------------------------


def _build_test_app(*, debug: bool = False) -> FastAPI:
    test_app = FastAPI()
    test_app.add_middleware(RequestContextMiddleware)
    for exception_type, handler in build_exception_handlers(FakeConfig(DEBUG=debug)).items():
        test_app.add_exception_handler(exception_type, handler)

    @test_app.get("/boom-classified")
    def boom_classified() -> None:
        raise ConfigurationError("bad config", field="LOG_LEVEL", hint="check .env")

    @test_app.get("/boom-unclassified")
    def boom_unclassified() -> None:
        _outer_layer()

    @test_app.get("/needs-int")
    def needs_int(n: int) -> dict[str, int]:
        return {"n": n}

    return test_app


client = TestClient(_build_test_app(), raise_server_exceptions=False)
debug_client = TestClient(_build_test_app(debug=True), raise_server_exceptions=False)


def test_classified_exception_is_logged_and_responds() -> None:
    with capture_logs() as logs:
        resp = client.get("/boom-classified")

    assert resp.status_code == 500
    body = resp.json()
    assert body["error"] == "configuration_error"
    assert body["message"] == "bad config"
    assert len(body["error_id"]) == 12
    # Internal context must not cross the boundary, even though it is in the log line below.
    assert "field" not in body
    assert "hint" not in body
    assert "debug" not in body

    (entry,) = [e for e in logs if e["event"] == "app_exception"]
    assert entry["error_code"] == "configuration_error"
    assert entry["field"] == "LOG_LEVEL"
    assert entry["hint"] == "check .env"
    assert entry["error_id"] == body["error_id"]
    assert entry["log_level"] == "error"
    # The three location layers.
    assert entry["raised_at"].startswith("tests/test_exceptions.py:")
    assert entry["failed_at"].startswith("tests/test_exceptions.py:")
    assert entry["blame"]["function"] == "_build_test_app.<locals>.boom_classified"


def test_unclassified_exception_is_logged_with_the_real_failing_line() -> None:
    with capture_logs() as logs:
        resp = client.get("/boom-unclassified")

    assert resp.status_code == 500
    assert resp.json()["error"] == "internal_error"
    assert resp.json()["message"] == "An unexpected error occurred."

    (entry,) = [e for e in logs if e["event"] == "unhandled_exception"]
    assert entry["exception_type"] == "ValueError"
    assert entry["exception_message"] == "the real cause"
    # Not the endpoint, not starlette — the actual line that raised, three layers down.
    assert entry["blame"]["function"] == "_innermost_failure"
    assert entry["app_traceback"][0].endswith("in _innermost_failure")
    assert any("boom_unclassified" in location for location in entry["app_traceback"])


def test_error_id_and_request_id_correlate_response_to_log() -> None:
    # merge_contextvars must be passed explicitly — capture_logs() disables configured processors,
    # so request_id would otherwise never reach the captured dicts.
    with capture_logs(processors=[structlog.contextvars.merge_contextvars]) as logs:
        resp = client.get("/boom-classified")

    body = resp.json()
    assert body["request_id"] == resp.headers["X-Request-ID"]
    (entry,) = [e for e in logs if e["event"] == "app_exception"]
    assert entry["request_id"] == body["request_id"]
    assert entry["error_id"] == body["error_id"]


def test_validation_error_uses_the_shared_envelope() -> None:
    with capture_logs() as logs:
        resp = client.get("/needs-int?n=abc")

    assert resp.status_code == 422
    body = resp.json()
    # FastAPI's default handler would have answered {"detail": [...]} — one shape for every error.
    assert body["error"] == "validation_error"
    assert body["errors"][0]["field"] == "query.n"
    assert "detail" not in body

    (entry,) = [e for e in logs if e["event"] == "request_validation_failed"]
    assert entry["log_level"] == "warning"  # the caller's mistake, not our defect
    assert entry["validation_errors"][0]["field"] == "query.n"


def test_not_found_uses_the_shared_envelope_and_logs_at_warning() -> None:
    with capture_logs() as logs:
        resp = client.get("/no-such-route")

    assert resp.status_code == 404
    assert resp.json()["error"] == "http_404"
    assert "detail" not in resp.json()

    (entry,) = [e for e in logs if e["event"] == "http_exception"]
    assert entry["log_level"] == "warning"
    assert entry["status_code"] == 404


def test_client_error_app_exception_logs_at_warning_not_error() -> None:
    class NotFoundError(AppException):
        error_code = "not_found"
        http_status_code = 404

    test_app = FastAPI()
    for exception_type, handler in build_exception_handlers(FakeConfig()).items():
        test_app.add_exception_handler(exception_type, handler)

    @test_app.get("/missing")
    def missing() -> None:
        raise NotFoundError("no such client")

    with capture_logs() as logs:
        resp = TestClient(test_app, raise_server_exceptions=False).get("/missing")

    assert resp.status_code == 404
    (entry,) = [e for e in logs if e["event"] == "app_exception"]
    assert entry["log_level"] == "warning"


# --------------------------------------------------------------------------------------
# The DEBUG boundary
# --------------------------------------------------------------------------------------


def test_debug_mode_adds_diagnostics_to_the_response() -> None:
    resp = debug_client.get("/boom-classified")

    debug = resp.json()["debug"]
    assert debug["exception"] == "ConfigurationError"
    assert debug["field"] == "LOG_LEVEL"
    assert debug["hint"] == "check .env"
    assert debug["raised_at"]["file"] == "tests/test_exceptions.py"


def test_debug_mode_adds_the_blame_frame_for_unclassified_errors() -> None:
    resp = debug_client.get("/boom-unclassified")

    debug = resp.json()["debug"]
    assert debug["exception_type"] == "ValueError"
    assert debug["blame"]["function"] == "_innermost_failure"


def test_debug_response_body_is_redacted() -> None:
    """A DEBUG body is a second sink for exception context, and the more exposed one — developers
    paste HTTP responses into tickets. Without sanitising it, a secret passed as debugging context
    would render verbatim in the response even though the log line redacts it."""
    test_app = FastAPI()
    for exception_type, handler in build_exception_handlers(FakeConfig(DEBUG=True)).items():
        test_app.add_exception_handler(exception_type, handler)

    @test_app.get("/leaky")
    def leaky() -> None:
        raise ConfigurationError("nope", api_key="sk-live-REALKEY", db_password="hunter2")

    resp = TestClient(test_app, raise_server_exceptions=False).get("/leaky")

    assert "sk-live-REALKEY" not in resp.text
    assert "hunter2" not in resp.text
    assert resp.json()["debug"]["api_key"] == "***"
    assert resp.json()["debug"]["db_password"] == "***"


def test_production_mode_leaks_nothing_from_an_unclassified_error() -> None:
    resp = client.get("/boom-unclassified")
    body = resp.json()

    assert "debug" not in body
    assert "the real cause" not in resp.text
    assert "_innermost_failure" not in resp.text
    assert set(body) == {"error", "message", "request_id"}
