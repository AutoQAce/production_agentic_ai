"""Custom exception hierarchy — foundational, used by every future layer.

Exceptions here are pure data/behavior: they carry an error code, an HTTP status, and structured
context, but never log or perform I/O themselves (SRP) — see `exception_handlers.py` for the one
place these get logged and turned into a response. New failure types subclass `AppException`; the
handler dispatches generically off the base contract, so adding a subclass never requires touching
the handler (OCP).

`log_context()` and `client_payload()` are deliberately two separate methods, not one dict a
handler picks fields out of — internal debugging context (raw values, field names, stack details)
must never reach a client response just because it was useful to log. Keeping that boundary here,
on the exception, means a handler can't get it wrong by accident; it only ever calls the method
for the sink it's writing to.
"""

from __future__ import annotations

from typing import Any


class AppException(Exception):
    """Base for every domain exception in this app.

    Subclass per failure type as each different layer is built. Every subclass must remain
    constructible as ``SubClass(message, **context)`` and keep the same three-member contract
    (`error_code`, `http_status_code`, `log_context()`) so the generic handler never needs to
    know which subclass it received (LSP).
    """

    error_code: str = "internal_error"
    http_status_code: int = 500

    def __init__(self, message: str, **context: Any) -> None:
        super().__init__(message)
        self.message = message
        self.context = context

    def log_context(self) -> dict[str, Any]:
        """Everything useful for root-causing this — logs only, never sent to a client."""
        return {"error_code": self.error_code, "message": self.message, **self.context}

    def client_payload(self) -> dict[str, Any]:
        """Everything — and only what — is safe to return to an API client.

        Deliberately excludes `self.context`. Override in a subclass if a specific field is
        genuinely meant to reach the client (e.g. which form field failed validation) — that
        becomes a visible, deliberate choice at the exception's own definition, not something
        a handler can leak by accident.
        """
        return {"error": self.error_code, "message": self.message}


class ConfigurationError(AppException):
    """Raised for missing or invalid environment configuration at startup."""

    error_code = "configuration_error"
    http_status_code = 500
