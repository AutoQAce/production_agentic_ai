"""Tests for structlog configuration + per-request lifecycle logging."""

import structlog
from fastapi.testclient import TestClient
from structlog.testing import capture_logs

from app.main import app

client = TestClient(app)


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
