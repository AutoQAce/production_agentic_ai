"""Custom exception hierarchy -- foundational, used by every future layer.

Exceptions here are pure data/behavior: they carry an error code, an HTTP status, structured context
and the code location they were raised from, but never log or perform I/O themselves (SRP) -- see
`exception_handlers.py` for the one place these get logged and turned into a response. New failure
types subclass `AppException`; the handler dispatches generically off the base contract, so adding a
subclass never requires touching the handler (OCP).

**Three separate audiences, three separate methods**, not one dict a handler picks fields out of:

  * `log_context()`   -- everything useful for root-causing. Logs only.
  * `client_payload()` -- the API contract. Safe for anyone, in any environment.
  * `debug_payload()` -- the developer's view, returned in the response **only** when DEBUG is on.

Internal debugging context (raw values, field names, code locations) must never reach a client
response just because it was useful to log. Keeping that boundary here, on the exception, means a
handler cannot get it wrong by accident; it only ever calls the method for the sink it is writing to.

**Every instance knows where it came from.** `__init__` captures the raise site via
`capture_origin()`, so `log_context()` reports the file, line and `Class.method` that raised -- even
for an exception that is caught, re-raised elsewhere, and logged three layers up with a traceback
that no longer starts anywhere near the real cause.
"""

from __future__ import annotations

import uuid
from typing import Any

from app.core.error_context import CodeOrigin, capture_origin


class AppException(Exception):
    """Base for every domain exception in this app.

    Subclass per failure type as each different layer is built. Every subclass must remain
    constructible as ``SubClass(message, **context)`` and keep the same contract (`error_code`,
    `http_status_code`, `log_context()`, `client_payload()`) so the generic handler never needs to
    know which subclass it received (LSP). `tests/test_exceptions.py` enforces that across every
    subclass automatically, including ones added later.
    """

    error_code: str = "internal_error"
    http_status_code: int = 500

    def __init__(self, message: str, *, hint: str | None = None, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.hint = hint
        self.context = context
        # Short, not a full UUID: this ends up in a user-visible error response and gets read aloud
        # in support tickets. 12 hex characters is ~10^14 combinations -- collision-free at any
        # volume this app will see, and short enough to type.
        self.error_id = uuid.uuid4().hex[:12]
        # `skip_instance=self` walks off the end of the constructor chain, so a subclass with its own
        # `__init__` -- however deep, and even when defined in the same file as the caller -- still
        # records *its caller's* line rather than a `super().__init__()` line. See `capture_origin`
        # for why counting stack levels and skipping by filename both fail here.
        self.origin: CodeOrigin | None = capture_origin(skip_instance=self)

    def log_context(self) -> dict[str, Any]:
        """Everything useful for root-causing this -- logs only, never sent to a client."""
        context: dict[str, Any] = {
            "error_id": self.error_id,
            "error_code": self.error_code,
            "message": self.message,
            **self.context,
        }
        if self.hint is not None:
            context["hint"] = self.hint
        if self.origin is not None:
            # `raised_at` is distinct from the traceback's blame frame: for an exception constructed
            # in one place and raised later, or re-raised after being caught, these differ -- and the
            # difference is usually the bug.
            context["raised_at"] = self.origin.location
            context["raised_in_module"] = self.origin.module
        return context

    def client_payload(self) -> dict[str, Any]:
        """Everything -- and only what -- is safe to return to an API client.

        Deliberately excludes `self.context`, `self.hint` and `self.origin`: context can hold raw
        input values, and a hint or a file path tells an attacker about the internals. Override in a
        subclass if a specific field is genuinely meant to reach the client (e.g. which form field
        failed validation) -- that becomes a visible, deliberate choice at the exception's own
        definition, not something a handler can leak by accident.

        `error_id` is included on purpose and is the only internal identifier that crosses the
        boundary: it is a random opaque token that reveals nothing, and it is what turns "it broke"
        into a one-query log lookup.
        """
        return {"error": self.error_code, "message": self.message, "error_id": self.error_id}

    def debug_payload(self) -> dict[str, Any]:
        """The developer's view of this failure, for a response body when DEBUG is on.

        Same information as `log_context()` minus nothing -- the point is that in development you
        should not have to leave the HTTP client to find out what happened. `exception_handlers.py`
        is responsible for never calling this outside DEBUG; this method just decides *what* a
        developer gets, keeping that judgement next to the exception that owns the data.
        """
        payload: dict[str, Any] = {"exception": type(self).__qualname__, **self.log_context()}
        if self.origin is not None:
            payload["raised_at"] = self.origin.as_dict()
        return payload


class ConfigurationError(AppException):
    """Raised for missing or invalid environment configuration at startup."""

    error_code = "configuration_error"
    http_status_code = 500
