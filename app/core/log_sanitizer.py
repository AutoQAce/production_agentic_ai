"""Leaf-value policy for log events: what must never leave the process, and what must never be
big enough to break the log pipeline.

Split from `logging.py` because it answers to a different owner and changes for different reasons
(SRP): the deny-list below is a security/compliance artifact, while `logging.py` owns the *shape*
of the pipeline. Both policies are applied in one traversal of the event dict rather than in two
processors -- an agent's event dict can carry a nested LLM payload, and walking it twice would
double the per-line cost for no benefit.

Registered as the last processor before rendering, so it also covers fields added by upstream
processors and by third-party libraries logging through stdlib.
"""

from __future__ import annotations

import re
from collections.abc import Mapping
from typing import Any

from pydantic import SecretStr

REDACTED = "***"

# Exact key names whose *value* is a credential, compared after normalisation (lowercased, with
# separators stripped -- so "API-Key", "api_key" and "apiKey" all collapse to "apikey").
# Data, not branches: covering a new credential field is one entry here (OCP).
_SENSITIVE_KEYS = frozenset(
    {
        "accesskey",
        "accesstoken",
        "apikey",
        "apitoken",
        "auth",
        "authorization",
        "bearer",
        "cardnumber",
        "clientsecret",
        "connectionstring",
        "cookie",
        "cvv",
        "dsn",
        "idtoken",
        "jwt",
        "passwd",
        "password",
        "privatekey",
        "refreshtoken",
        "secret",
        "secretkey",
        "sessionkey",
        "setcookie",
        "signature",
        "ssn",
        "token",
    }
)

# Substring matches against the same normalised key, for the compound names a fixed list cannot
# enumerate ("db_password", "openai_api_key", "user_credentials").
#
# `token` is deliberately NOT a fragment: `prompt_tokens` / `completion_tokens` / `total_tokens`
# are the cost and throughput metrics of an agentic system, and redacting them would blind the
# thing this pipeline exists to observe. Bare `token` is caught by _SENSITIVE_KEYS instead.
_SENSITIVE_FRAGMENTS = (
    "apikey",
    "authorization",
    "authtoken",
    "bearertoken",
    "cooki",  # truncated on purpose: covers "cookie" and "cookies" without listing both
    "credential",
    "creditcard",
    "passphrase",
    "password",
    "privatekey",
    "secret",
)

_KEY_NOISE = re.compile(r"[^a-z0-9]")

# An LLM prompt or completion is unbounded; a log line is not. Aggregators drop or clip oversized
# lines, which loses the *whole* event including the fields you actually needed -- so cap the
# offending value here, where the cap is visible and greppable, rather than at the collector.
_MAX_VALUE_CHARS = 2_000
_MAX_COLLECTION_ITEMS = 50
_MAX_DEPTH = 6

# Live objects consumed further down the chain, not data: `exc_info` is a traceback tuple and
# `stack_info` is already-rendered text. Walking them is wrong as well as expensive.
_PASSTHROUGH_KEYS = frozenset({"exc_info", "stack_info"})


def _is_sensitive(key: str) -> bool:
    """True when a key's *value* is a credential and must be replaced rather than logged."""
    normalised = _KEY_NOISE.sub("", key.lower())
    return normalised in _SENSITIVE_KEYS or any(fragment in normalised for fragment in _SENSITIVE_FRAGMENTS)


def _cap_text(value: str) -> str:
    """Truncate an oversized string, keeping the original length visible in the marker."""
    if len(value) <= _MAX_VALUE_CHARS:
        return value
    return f"{value[:_MAX_VALUE_CHARS]}...[truncated, {len(value)} chars total]"


def _sanitise_value(value: Any, depth: int) -> Any:
    """Apply leaf policy to one value, recursing into containers up to `_MAX_DEPTH`."""
    if isinstance(value, SecretStr):
        # Redacted by type, not by key name: a SecretStr is never loggable regardless of the key it
        # was bound under. `repr()` would already mask it, but this keeps one marker in the output.
        return REDACTED
    if isinstance(value, str):
        return _cap_text(value)
    if isinstance(value, bytes):
        return _cap_text(value.decode("utf-8", errors="replace"))
    if isinstance(value, Mapping):
        if depth >= _MAX_DEPTH:
            return f"[nested mapping elided at depth {_MAX_DEPTH}]"
        return _sanitise_mapping(value, depth + 1)
    if isinstance(value, (list, tuple, set, frozenset)):
        if depth >= _MAX_DEPTH:
            return f"[nested collection elided at depth {_MAX_DEPTH}]"
        return _sanitise_collection(value, depth + 1)
    # Scalars (int/float/bool/None) and anything exotic pass through to the renderer's fallback.
    return value


def _sanitise_mapping(mapping: Mapping[Any, Any], depth: int) -> dict[str, Any]:
    """Rebuild a mapping with sensitive keys redacted and oversized values capped."""
    return {
        str(key): REDACTED if _is_sensitive(str(key)) else _sanitise_value(value, depth)
        for key, value in mapping.items()
    }


def _sanitise_collection(collection: Any, depth: int) -> list[Any]:
    """Rebuild a collection, keeping at most `_MAX_COLLECTION_ITEMS` entries."""
    items = list(collection)
    kept: list[Any] = [_sanitise_value(item, depth) for item in items[:_MAX_COLLECTION_ITEMS]]
    if len(items) > _MAX_COLLECTION_ITEMS:
        kept.append(f"...[truncated, {len(items)} items total]")
    return kept


def sanitise(mapping: Mapping[str, Any]) -> dict[str, Any]:
    """Redact credential-shaped keys and cap oversized values in one flat mapping.

    The policy itself, independent of structlog. Exposed separately from the processor below because
    log lines are not the only sink that must never carry a secret: `exception_handlers.py` runs a
    DEBUG-mode response body through this too. A leak-prevention rule that only guards one sink is a
    rule with a hole in it.

    Returns a new dict rather than mutating in place, so a caller's own object is never altered by
    the act of logging or reporting it.
    """
    sanitised: dict[str, Any] = {}
    for key, value in mapping.items():
        if key.startswith("_") or key in _PASSTHROUGH_KEYS:
            sanitised[key] = value
        elif _is_sensitive(key):
            sanitised[key] = REDACTED
        else:
            sanitised[key] = _sanitise_value(value, depth=0)
    return sanitised


def sanitise_event_dict(_logger: Any, _method_name: str, event_dict: Mapping[str, Any]) -> dict[str, Any]:
    """structlog processor adapter over `sanitise()`. Registered last in the processor chain."""
    return sanitise(event_dict)
