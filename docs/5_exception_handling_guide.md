# 🧯 `exceptions.py` + `error_context.py` + `exception_handlers.py` — Line-by-Line Guide

> **Purpose:** A personal reference covering **every line** of this project's exception handling —
> three files, because they are one design split across three owners. For each line: what it means in
> plain English, **what breaks if you don't write it**, the technical mechanism, why *this* way and
> not the obvious alternatives, and where it fits in a production agentic AI system.
>
> **Written:** 2026-08-19, after building the whole error path from scratch (the source article has no
> exception module at all) against one requirement: *from the log line alone, know the exact file,
> line, class and function that failed.* Verifying it turned up **two bugs in the mechanism, two
> latent bugs in the app, one security hole, and a 40-millisecond performance defect** — all listed
> below.
> **Companion docs:** [`4_logging_guide.md`](./4_logging_guide.md) — the pipeline these log lines
> travel through, and the redaction they pass. [`3_config_py_guide.md`](./3_config_py_guide.md) —
> where `DEBUG` comes from.

---

## 🚨 Read this first — six things that verification found

Nothing in this table was predicted. Every row came from running the code and being wrong.

| # | Belief / symptom | What actually happens | Fix |
|---|---|---|---|
| 1 | `capture_origin` can find the raise site by skipping frames from `exceptions.py` | **Broken.** Fails exactly when a subclass is defined *in the same file as the raiser* — the common case for a locally-defined error. It then blamed the `super().__init__()` line. Counting stack levels fails too (every subclass `__init__` shifts the depth). | Identity-based: skip every frame whose `self` **is** the object being constructed (§17) |
| 2 | `is_first_party("<string>")` is obviously `False` | **Returned `True`.** `Path("<string>").resolve()` silently anchors to the CWD, and the CWD *is* the project root — so every synthetic frame was reported as our own code. | Reject `<…>` names *before* `resolve()` (§13) |
| 3 | An unhandled exception is logged once | **Logged twice, with two full tracebacks.** Probed the stack: `ServerErrorMiddleware` → your middleware → `ExceptionMiddleware`. An `AppException` is converted *inside*, so middleware never sees it, but an unclassified error passes through **both**. | Middleware logs a lifecycle line only, no `exc_info` (§28) |
| 4 | Every error answers in our envelope | **422 and 404 escaped entirely.** FastAPI registers its own `RequestValidationError` and `HTTPException` handlers *before* yours, so they answered `{"detail": …}` while everything else answered `{"error", "message", "error_id"}`. | Both claimed explicitly (§25) |
| 5 | The sanitizer protects every sink | **It protected only logs.** The `DEBUG=true` response body rendered `"api_key": "sk-live-…"` **verbatim** while the log line redacted it — and a response is the *more* exposed sink. | `sanitise()` extracted as the policy; debug bodies pass through it (§21) |
| 6 | Frame introspection is cheap; errors are rare | **`describe()` cost 40 ms** on a 22-frame traceback and 9.1 ms on a 6-frame one. Constructing one `AppException` cost **629 µs** vs `ValueError`'s 0.08 µs — 7,000× slower. `Path.resolve()` is a **syscall**, called 3× per frame, and the traceback was walked twice. | `@lru_cache` on path classification + one walk → **39 µs / 5.3 µs** (§13, §26) |

**The meta-lesson:** diagnostics are code, and untested diagnostic code fails in the one situation it
exists for. Rows 3, 4 and 5 were all *silent* — the app returned 200s, the tests passed, and the
defect only appeared when something broke. Row 6 is worse than silent: it made the error path slowest
exactly when errors arrive in bursts. **Write a test that asserts on the diagnostic output itself,
and benchmark the failure path, not just the happy one.**

---

## 📚 Table of Contents

| § | Section | File | Lines |
|---|---|---|---|
| 1 | [What these three files are](#1-what-these-three-files-are) | all | — |
| 2 | [The three-layer location model](#2-the-three-layer-location-model) | all | — |
| 3 | [Why three files and not one](#3-why-three-files-and-not-one) | all | — |
| 4 | [Docstring — the contract](#4-exceptionspy-docstring--lines-123) | `exceptions.py` | 1–23 |
| 5 | [Imports](#5-imports--lines-2530) | `exceptions.py` | 25–30 |
| 6 | [`AppException` + class attributes](#6-appexception--lines-3344) | `exceptions.py` | 33–44 |
| 7 | [`__init__` — every instance knows where it came from](#7-__init__--lines-4659) | `exceptions.py` | 46–59 |
| 8 | [`log_context()`](#8-log_context--lines-6177) | `exceptions.py` | 61–77 |
| 9 | [`client_payload()`](#9-client_payload--lines-7992) | `exceptions.py` | 79–92 |
| 10 | [`debug_payload()`](#10-debug_payload--lines-94105) | `exceptions.py` | 94–105 |
| 11 | [`ConfigurationError`, and the taxonomy that isn't there](#11-configurationerror--lines-108112) | `exceptions.py` | 108–112 |
| 12 | [Docstring + constants](#12-error_contextpy-docstring--constants--lines-143) | `error_context.py` | 1–43 |
| 13 | [`_classify` — the load-bearing cache](#13-_classify--lines-4692) | `error_context.py` | 46–92 |
| 14 | [`CodeOrigin`](#14-codeorigin--lines-95122) | `error_context.py` | 95–122 |
| 15 | [`_origin_from_frame` — where the class name comes from](#15-_origin_from_frame--lines-125139) | `error_context.py` | 125–139 |
| 16 | [`capture_origin`](#16-capture_origin--lines-142166) | `error_context.py` | 142–166 |
| 17 | [`_is_internal_frame` — the identity trick](#17-_is_internal_frame--lines-169181) | `error_context.py` | 169–181 |
| 18 | [`_exception_chain`](#18-_exception_chain--lines-184203) | `error_context.py` | 184–203 |
| 19 | [`first_party_frames` — innermost first](#19-first_party_frames--lines-206224) | `error_context.py` | 206–224 |
| 20 | [`blame_frame` + `describe`](#20-blame_frame--describe--lines-227275) | `error_context.py` | 227–275 |
| 21 | [Docstring + `ErrorDetailConfig`](#21-exception_handlerspy-docstring--config--lines-164) | `exception_handlers.py` | 1–64 |
| 22 | [`_request_id`](#22-_request_id--lines-6774) | `exception_handlers.py` | 67–74 |
| 23 | [`_log_error` — the `exc_info` discovery](#23-_log_error--lines-7785) | `exception_handlers.py` | 77–85 |
| 24 | [`_error_response` — one envelope](#24-_error_response--lines-88118) | `exception_handlers.py` | 88–118 |
| 25 | [`build_exception_handlers` — the registry](#25-build_exception_handlers--lines-121213) | `exception_handlers.py` | 121–213 |
| 26 | [Measured performance](#26-measured-performance) | all | — |
| 27 | [What a real failure looks like](#27-what-a-real-failure-looks-like) | all | — |
| 28 | [Middleware integration + the stack order](#28-middleware-integration--the-stack-order) | `middleware.py` | 27–51 |
| 29 | [SOLID scorecard](#29-solid-scorecard) | all | — |
| 30 | [Where this fits in the 7 layers](#30-where-this-fits-in-the-7-layers) | all | — |
| 31 | [How to extend it](#31-how-to-extend-it) | all | — |
| 32 | [Cheat sheet](#32-cheat-sheet) | all | — |

---

## 1. What these three files are

🍕 **Plain terms:** an **air-crash investigation team.**

`exceptions.py` is the **flight recorder** bolted into every aircraft. The moment something goes
wrong it stamps the exact position — file, line, class, method — into the box itself. It does not
radio anyone, it does not decide what to tell the press; it records.

`error_context.py` is the **investigator** who arrives at the wreckage. There are forty pieces of
debris — engine, avionics, airframe, three suppliers' parts — and Python's traceback hands them over
in the least useful order, with somebody else's component on top. The investigator's whole job is to
point at **the one part that was ours** and say *start here*.

`exception_handlers.py` is the **press office plus the archive**. It writes two documents from the
same accident: an exhaustive internal report (the log line) and a short public statement (the HTTP
response). It is emphatically not allowed to confuse the two.

🔧 **Technical:** an exception hierarchy that captures its own construction site, a stack-introspection
module that extracts the deepest first-party frame from an exception chain, and four FastAPI exception
handlers that emit a structured log record (summary fields + full `exc_info`) and a single consistent
JSON error envelope.

### The one idea behind all three files

> **A failure must name the line that caused it, in a field you can query, without telling the client anything.**

Every decision below is a consequence. *Name the line* is `capture_origin` and `blame_frame`. *In a
field you can query* is why `failed_at` exists next to the traceback rather than inside it. *Without
telling the client* is the three-method split on `AppException` and the DEBUG boundary.

---

## 2. The three-layer location model

This is the part worth remembering; everything else is mechanism.

A production stack for one agent request is 40+ frames deep — uvicorn → starlette → fastapi → your
endpoint → your service → langchain → httpx → ssl. Python puts the **innermost frame last**, and that
frame is almost always somebody else's code. So a raw traceback answers "what broke" but not "what of
*mine* broke", and it answers nothing you can put in a dashboard.

Three fields fix that, and each answers a different question:

| Field | Source | Question it answers |
|---|---|---|
| `raised_at` | the exception itself, at construction (§7) | Where did **we decide** this was an error? |
| `failed_at` / `blame` | the traceback's deepest first-party frame (§20) | Which line do I **go and read**? |
| `app_traceback` | every first-party frame, innermost first (§19) | What **path through our layers** led here? |

Plus `exc_info`, so the renderer attaches the complete formatted chain.

❓ **Why not just the traceback?** Because you cannot facet a dashboard on a multi-line string. These
three are flat and short, so `failed_at:"app/services/llm.py:50 in LLMService.invoke"` is a log query.
The traceback is what you read *after* the query has found the line.

❓ **Why is `raised_at` separate from `failed_at`?** For a simple `raise`, they are identical. They
diverge when an exception is constructed in one place and raised in another, or caught and re-raised
several layers up — **and that divergence is usually the bug.** Two fields cost nothing and make it
visible; one field would hide it.

---

## 3. Why three files and not one

Split by **who files the change request**, which is the only definition of Single Responsibility that
survives a real codebase:

| Change request | Lands in | Comes from |
|---|---|---|
| "Add a `RateLimitError` with a 429" | `exceptions.py` | whoever builds the auth layer |
| "Never leak the provider's raw message" | `exceptions.py` | security |
| "Blame frames should skip our own middleware" | `error_context.py` | whoever debugs at 3am |
| "Log 404s at WARNING, not ERROR" | `exception_handlers.py` | on-call, after an alert storm |
| "Error responses need a `retryable` flag" | `exception_handlers.py` | the API consumer |

⚠️ **The coupling this creates:** exactly two import edges — `exceptions.py` → `error_context.py`
(for `capture_origin`), and `exception_handlers.py` → both (plus `log_sanitizer`). `error_context.py`
imports **nothing from this project**: only `sys`, `traceback`, `dataclasses`, `functools`, `pathlib`,
`types`. That is deliberate; it is the piece most likely to be lifted into another project wholesale.

---

## 4. `exceptions.py` docstring — lines 1–23

```python
"""Custom exception hierarchy -- foundational, used by every future layer.

Exceptions here are pure data/behavior: they carry an error code, an HTTP status, structured context
and the code location they were raised from, but never log or perform I/O themselves (SRP) -- see
`exception_handlers.py` for the one place these get logged and turned into a response.
```

❓ **Why "never log or perform I/O themselves":** the tempting design is
`raise ConfigurationError("bad")` that logs itself in `__init__`. It fails three ways: an exception
caught and handled would still have logged an error that never happened; the same failure logs twice
when a handler logs it again; and an exception constructed in a test writes to your log pipeline.
Recording *where* it was constructed is free and side-effect-less. Recording *that it happened* is
the handler's call, because only the handler knows whether it was handled.

> **The transferable idea:** an exception is a **value**, not an event. Constructing one says
> "this situation exists", not "something has gone wrong for the user" — only the code that fails to
> handle it can say that.

---

## 5. Imports — lines 25–30

```python
from __future__ import annotations

import uuid
from typing import Any

from app.core.error_context import CodeOrigin, capture_origin
```

Two imports from the project, and that is the entire dependency surface. Note what is **absent**:
no `logging`, no `structlog`, no `fastapi`. If any of those appear here, the SRP boundary in §4 has
been broken.

---

## 6. `AppException` — lines 33–44

```python
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
```

🔧 **Technical:** two **class** attributes, not instance fields. A subclass overrides them with one
line each and inherits everything else.

❓ **Why class attributes rather than `__init__` parameters:** `error_code` is a property of the
*failure type*, not of one occurrence. Passing it per-instance would let two raises of the same class
report different codes, which breaks every dashboard built on `error_code`.

🚨 **The LSP claim is enforced, not asserted.** `test_every_app_exception_subclass_honors_the_base_contract`
walks `__subclasses__()` **recursively** and parametrises over every subclass that exists, so a
subclass added in six months is tested the day it is written:

```python
def _all_subclasses(cls: type) -> Iterator[type]:
    """Every subclass, however deep — so this test picks up new AppException types automatically."""
    for sub in cls.__subclasses__():
        yield sub
        yield from _all_subclasses(sub)
```

❓ **Why not `@abstractmethod` instead?** It catches strictly less. `abstractmethod` on
`log_context()` would prove the method *exists*; it cannot catch a subclass whose `__init__` forgets
`**context` or skips `super().__init__()` — which is the failure that actually happens, and which
silently drops `error_id` and `origin`. The test constructs each subclass and checks the *behaviour*.

---

## 7. `__init__` — lines 46–59

```python
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
```

🔧 **`*` makes `hint` keyword-only.** Verified — `ConfigurationError("msg", "positional hint")` raises:

```
TypeError: AppException.__init__() takes 2 positional arguments but 3 were given
```

❓ **Why force that:** the signature is `(message, **context)`. Without the `*`, a second positional
argument would be ambiguous to a reader and impossible to extend later. Asserted by the verification
run; the keyword-only form also means `**context` can never accidentally swallow a `hint=`.

❓ **Why `error_id` at all?** It is the only field that appears in **both** the HTTP response and the
log line. A user sends a screenshot saying `error_id: 102fad90e3b9`; that is one log query away from
the full traceback. Without it, "the site broke around 2pm" is your entire search key.

❓ **Why 12 hex characters and not a full UUID?** Measured keyspace: 16¹² = **281,474,976,710,656**.
Collision-free at any volume this app will see (verified: 5,000 generated, zero collisions), and short
enough that a support agent can read it over the phone. A 36-character UUID with hyphens gets
transcribed wrong.

⚠️ **This is not a cryptographic token.** It is `uuid4` truncated, so it is unguessable enough to
reveal nothing, but do not use it for authorisation. It identifies a log line, nothing else.

🚨 **`skip_instance=self` is the fix for finding #1.** See §17 for why the two obvious alternatives
both fail. Asserted by `test_subclass_with_its_own_init_still_records_the_callers_line`.

---

## 8. `log_context()` — lines 61–77

```python
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
```

🍕 **Plain terms:** the internal incident report. Everything the investigator wants, none of it
cleared for publication.

❓ **Why `**self.context` last-but-not-least:** it comes after the three fixed keys so a caller can
*override* `message` if they mean to, but before `hint`/`raised_at`, which are the exception's own
facts and must not be shadowed by a stray `raised_at=` in a call site's kwargs.

🎯 **Agentic AI angle:** `**self.context` is where the agent-specific detail goes, and it is why this
is a dict rather than a fixed set of fields: `provider="openai"`, `model="gpt-5.4-mini"`,
`attempt=3`, `tool="search_filings"`, `prompt_tokens=812`. None of those exist in an ordinary web
service's error model, and all of them are the first thing you want when an agent misbehaves.

⚠️ **Anything you put in `context` reaches the log pipeline** — which is exactly why
[`log_sanitizer.py`](../app/core/log_sanitizer.py) runs last in that pipeline. `api_key="sk-live-…"`
passed as context renders as `"api_key": "***"`, verified end-to-end by
`test_credentials_are_redacted_end_to_end` and, for the response body, `test_debug_response_body_is_redacted`.

---

## 9. `client_payload()` — lines 79–92

```python
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
```

🚨 **The whole point of having two methods instead of one dict.** The alternative — one
`to_dict()` that handlers pick fields out of — puts the leak decision in the *handler*, where it has
to be re-made correctly for every failure type, forever. Here it is made **once, on the exception**,
and a handler physically cannot leak `context` because it never receives it.

❓ **Why is `hint` excluded?** A hint like `"check the provider status page"` is harmless; a hint like
`"add it to ENVIRONMENT_TIERS"` names your internal config structure. Rather than judge each one,
hints are internal by default and a subclass can override this method to promote a specific one.
Asserted by `test_hint_reaches_logs_and_debug_but_never_the_client`.

✅ **Verified in production mode:** `test_production_mode_leaks_nothing_from_an_unclassified_error`
asserts the response body keys are **exactly** `{"error", "message", "request_id"}` and that neither
the exception message nor the failing function name appears anywhere in the response text.

---

## 10. `debug_payload()` — lines 94–105

```python
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
```

🍕 **Plain terms:** the report you hand a colleague standing next to you, versus the one you post
publicly. Same accident, no redactions for an audience that already has the keys.

🔧 **`raised_at` is overwritten** — `log_context()` set it to the flat `location` string; here it
becomes the full `as_dict()` with separate `file`/`line`/`function`/`module`. A developer reading JSON
in an HTTP client wants the structured form; a log aggregator wants the flat string.

⚠️ **This method is the reason finding #5 existed.** It returns `log_context()`, which can contain
credentials passed as debugging context. It is *correct* for this method to return them — the
developer's view holds everything — and it is the **handler's** job to sanitise before shipping it
over HTTP (§24). Splitting the responsibility that way is deliberate, but it means this method is a
loaded gun: anything that calls it and does not sanitise leaks.

---

## 11. `ConfigurationError` — lines 108–112

```python
class ConfigurationError(AppException):
    """Raised for missing or invalid environment configuration at startup."""

    error_code = "configuration_error"
    http_status_code = 500
```

Two lines of override, which is the OCP payoff: everything in §7–10 comes for free.

⚠️ **The taxonomy that is deliberately not here.** There is no `NotFoundError`, `RateLimitError`,
`LLMProviderError`, `ToolExecutionError` or `GuardrailViolation` — even though this is an agentic AI
app and all five are coming. Inventing them now would be scaffolding for layers that do not exist:
each one needs a status code, a client message and a redaction decision that can only be made
sensibly with the calling code in front of you.

**The trigger:** add each subclass in the commit that first raises it. The handler never changes —
verified by the registry dispatch test in §25, where a subclass **two levels** below `AppException`
still routes correctly.

Also absent: `AppException.wrap(exc)` for converting a third-party exception while preserving the
cause. It is the right helper for wrapping `httpx`/`openai` errors, and there is no LLM code yet to
wrap. `raise LLMProviderError(...) from exc` already does the job (§18 reads `__cause__`).

---

## 12. `error_context.py` docstring + constants — lines 1–43

```python
# app/core/error_context.py -> app/core -> app -> <project root>. Same derivation as config.py, for
# the same reason: it must not depend on the working directory uvicorn or pytest was launched from.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
_VENV_DIR = PROJECT_ROOT / ".venv"

# How many of our own frames to keep. First-party frames are few by nature (endpoint -> service ->
# client); the cap only guards against runaway recursion producing a log line thousands of frames long.
_MAX_FIRST_PARTY_FRAMES = 15

# How far to follow `__cause__` / `__context__`. Chains longer than this are pathological, and each
# link costs another full frame walk.
_MAX_CHAIN_DEPTH = 5
```

❓ **Why `PROJECT_ROOT` and not the `app/` package as the first-party boundary:** a failure raised
from `tests/` or `scripts/` is still your code and still the frame worth reporting. Verified — the
benchmark in `scripts/` reports `scripts/bench_error_context.py:17 in _nested` as its blame frame,
and every test in `tests/` gets a `tests/test_exceptions.py` blame frame.

⚠️ **The consequence:** code living **outside** the project root is not first-party, so blame falls
back to the deepest frame available. A scratch script importing `app` gets
`app/core/middleware.py` as its blame frame — correct behaviour, surprising the first time you see it.
It is why the benchmark lives in `scripts/` inside the repo rather than in a temp directory.

**Both caps are verified, not decorative:**

| Cap | Test | Result |
|---|---|---|
| `_MAX_FIRST_PARTY_FRAMES = 15` | `test_first_party_frames_are_capped` — 60-deep recursion | exactly 15 kept, **innermost first** |
| `_MAX_CHAIN_DEPTH = 5` | 21-link `__cause__` chain built by hand | chain truncated to 5, `caused_by` has 4 entries |

🎯 **Agentic AI angle on the frame cap:** an agent loop that re-enters itself — a planner calling a
sub-agent calling the planner — produces genuinely deep first-party stacks, not just pathological
recursion. Without the cap, one runaway agent writes a log line with thousands of frames, and the
aggregator drops the whole event (the same failure mode the value caps in
[`log_sanitizer.py`](../app/core/log_sanitizer.py) exist to prevent).

---

## 13. `_classify` — lines 46–92

The most important function in the file, and it started as three functions with a 40-millisecond bug.

```python
@lru_cache(maxsize=2048)
def _classify(filename: str) -> tuple[str, bool]:
    """`(display path, is_first_party)` for one source filename. Both answers, one resolution.
```

```python
    if not filename or filename.startswith("<"):
        return filename, False
    try:
        resolved = Path(filename).resolve()
    except (OSError, ValueError):
        # A filename containing a NUL byte or otherwise invalid for this platform.
        return filename, False

    if _VENV_DIR not in resolved.parents and (PROJECT_ROOT == resolved or PROJECT_ROOT in resolved.parents):
        return resolved.relative_to(PROJECT_ROOT).as_posix(), True
    # Dependency frames: `httpx/_client.py` beats both a bare filename (ambiguous across packages)
    # and the full site-packages path (80 characters of build-machine layout).
    return f"{resolved.parent.name}/{resolved.name}", False
```

🍕 **Plain terms:** the investigator's **parts catalogue**. Look up a serial number once, learn both
"is this ours?" and "what do we call it in the report?", and never look it up again — the catalogue
does not change mid-investigation.

🚨 **The cache is load-bearing, not an optimisation (finding #6).** `Path.resolve()` is a filesystem
syscall. Before caching, it ran **three times per frame** (display path, first-party flag, and the
flag again from *inside* the display path), on every frame of every walk, and `describe()` walked the
traceback twice. Measured:

| | before | after | factor |
|---|---|---|---|
| `describe()`, 5-frame traceback | 9,138 µs | **10.7 µs** | **854×** |
| `describe()`, 22-frame traceback | 40,284 µs | **39.1 µs** | **1,030×** |
| `AppException()` construction | 628.8 µs | **5.3 µs** | **119×** |
| one classification, cold → warm | 353 µs | **0.062 µs** | **5,670×** |

Reproduce with `uv run python scripts/bench_error_context.py`.

❓ **Why is this safe to cache?** `co_filename` takes one distinct value per source file, so a process
sees a few hundred keys — `maxsize=2048` never evicts in practice. And a file's path cannot change
within a process, so there is nothing to invalidate. Verified: `_classify.cache_info()` after 200,000
warm calls reports `hits=200000, misses=1, currsize=1`. Asserted by `test_path_classification_is_cached`.

🚨 **The `startswith("<")` guard is finding #2, and it must come before `resolve()`.**
`Path("<string>").resolve()` does not raise — it **silently anchors to the current working
directory**, which for this project *is* `PROJECT_ROOT`. So every synthetic frame (`<string>`,
`<stdin>`, `<listcomp>`, `<frozen importlib._bootstrap>`) was classified as first-party, and a
comprehension or an `exec` could become your blame frame. Asserted by
`test_non_paths_are_never_first_party`, parametrised over four such names.

❓ **Why return a tuple instead of two cached functions:** two `@lru_cache`ed functions would each
call `resolve()` on a cache miss — two syscalls per new file instead of one — and could in principle
disagree. One function, one resolution, two answers that are always consistent by construction.

❓ **Why `f"{resolved.parent.name}/{resolved.name}"` for dependencies:** `_client.py` alone is
ambiguous (httpx, httpcore and openai all have one); the full site-packages path is 80 characters of
your build machine's directory layout. `httpx/_client.py` is the useful middle. Asserted by
`test_display_path_shortens_dependency_paths`.

```python
def is_first_party(filename: str) -> bool: ...
    return _classify(filename)[1]


def _display_path(filename: str) -> str:
    """A path short enough to read in a log line but specific enough to open in an editor."""
    return _classify(filename)[0]
```

Both are one-line views on the cached tuple. `is_first_party` stays public because it is the
conceptual boundary of the whole module and tests assert on it directly.

> **The transferable idea:** when a "diagnostic" helper runs on the failure path, **benchmark it on
> the failure path.** Nothing about this code looked slow, no test was slow, and it would have added
> 40 ms per error to a service under exactly the load that produces errors.

---

## 14. `CodeOrigin` — lines 95–122

```python
@dataclass(frozen=True, slots=True)
class CodeOrigin:
    """One point in the codebase: the unit every diagnostic field in this project is built from.

    Frozen because it is a fact about a moment that has already happened -- nothing downstream has
    any business editing it.
    """

    file: str
    line: int
    function: str
    module: str
    first_party: bool

    @property
    def location(self) -> str:
        """`app/services/llm.py:42 in LLMService.invoke` -- one greppable string for a log line."""
        return f"{self.file}:{self.line} in {self.function}"
```

🔧 **`frozen=True, slots=True`** — verified: assigning `origin.line = 2` raises
`dataclasses.FrozenInstanceError`, and the instance has **no `__dict__`**.

❓ **Why `slots=True`:** one `CodeOrigin` is created per frame, so a 22-frame traceback allocates 22
of them and the frame cap allows 15 per chain link. `slots` removes the per-instance dict — less
memory and faster attribute access on the path that is already the most expensive part of error
handling (§13).

❓ **Why both `location` (a string) and `as_dict()` (a mapping):** two consumers with opposite needs.
A log aggregator wants `failed_at` as one flat greppable string it can facet on; a developer reading
a DEBUG response wants `file`/`line` as separate fields. Producing both from one source means they
can never disagree.

---

## 15. `_origin_from_frame` — lines 125–139

```python
def _origin_from_frame(frame: FrameType, lineno: int | None = None) -> CodeOrigin:
    """Build a `CodeOrigin` from a live frame.

    `co_qualname` (Python 3.11+) is what makes the *class* visible: it yields
    `LLMService.invoke` where `co_name` would only give `invoke`, and "which class" is half of
    "where is this failing" in a codebase with several implementations of one Protocol.
    """
    code = frame.f_code
    return CodeOrigin(
        file=_display_path(code.co_filename),
        line=lineno if lineno is not None else frame.f_lineno,
        function=code.co_qualname,
        module=frame.f_globals.get("__name__", "<unknown>"),
        first_party=is_first_party(code.co_filename),
    )
```

🚨 **`co_qualname` is what satisfies the "show me the class" requirement.** It is a Python 3.11
addition (this project pins `>=3.12`). Verified — a method on a locally-defined class reports
`test_capture_origin_reports_the_class_not_just_the_method.<locals>.Worker.run`, and the demo reports
`LLMService.invoke`. With `co_name` you would get `run` and `invoke`: useless in a codebase where
three classes implement the same Protocol with the same method names.

❓ **Why does `lineno` come in as a parameter?** Because there are two sources of truth. For a **live**
frame (`capture_origin`), `frame.f_lineno` is where execution currently is. For a **traceback** frame,
`traceback.walk_tb` yields the line where the exception passed through — which is *not*
`frame.f_lineno`, because the frame object has moved on. Using `f_lineno` for traceback frames would
report the wrong line, subtly and only sometimes.

❓ **Why `f_globals.get("__name__", "<unknown>")` and not `[...]`:** a frame from `exec()` or a
synthetic code object may have no `__name__`. A `KeyError` from the diagnostic layer while handling
an exception would replace a useful error with a confusing one.

---

## 16. `capture_origin` — lines 142–166

```python
def capture_origin(skip_instance: object | None = None) -> CodeOrigin | None:
    """Where the caller is, skipping this module and any constructor frame of `skip_instance`.

    Used by `AppException.__init__` to record the `raise` site. The raise site is **not at a fixed
    stack depth**, so counting stack levels cannot work: a subclass that defines its own `__init__`
    and calls `super().__init__()` adds a frame, and a two-level hierarchy adds two.
```

```python
    try:
        frame: FrameType | None = sys._getframe(1)
    except (ValueError, AttributeError):  # pragma: no cover - CPython always provides this
        return None
    while frame is not None:
        if not _is_internal_frame(frame, skip_instance):
            return _origin_from_frame(frame)
        frame = frame.f_back
    return None
```

🔧 **`sys._getframe(1)`** starts at the caller. The leading underscore marks it CPython-specific — it
does not exist on all implementations, hence the `AttributeError` guard.

❓ **What if we don't write the try/except:** on a Python without `_getframe`, importing and raising
any `AppException` would fail with `AttributeError` *while handling an error*. The `# pragma: no
cover` is honest: CPython always provides it, so the branch is unreachable here and marked rather
than faked with a contrived test.

❓ **Why return `None` rather than raise on failure:** stated in the docstring — "a diagnostic aid must
never be the reason a request fails". Every consumer treats `origin` as optional (`if self.origin is
not None`), so a missing origin degrades the log line and breaks nothing.

---

## 17. `_is_internal_frame` — lines 169–181

The fix for finding #1, and the cleverest fifteen lines in the three files.

```python
def _is_internal_frame(frame: FrameType, skip_instance: object | None) -> bool:
    """True for frames that are plumbing rather than the caller we are looking for."""
    # Plain string comparison, no `resolve()`: `__file__` is absolute since Python 3.9, and a
    # function defined in this module always reports exactly that string as its `co_filename`. No
    # path normalisation means no exception to guard against.
    if frame.f_code.co_filename == __file__:
        return True
    if skip_instance is None:
        return False
    # `f_locals.get("self") is skip_instance` identifies a constructor (or any method) frame of the
    # very object being built -- identity, not name matching, so it cannot be fooled by a subclass
    # that renames things or by an unrelated local called `self`.
    return frame.f_locals.get("self") is skip_instance
```

🍕 **Plain terms:** you are looking for who *ordered* the part, and you are standing in a room full of
people who *assembled* it. Rather than counting how many assemblers there are — which changes per
model — you ask each person "are your hands on this exact object?" and walk past everyone who says yes.

🚨 **Three approaches, two of which are broken.** This is worth remembering because the broken ones
look fine:

| Approach | Fails when | Symptom |
|---|---|---|
| `sys._getframe(2)` — count levels | any subclass defines `__init__` | blames `super().__init__()`; every extra hierarchy level shifts it again |
| skip frames from `exceptions.py` | the subclass is defined **in the caller's own file** | blames the subclass's `super().__init__()` line — and a locally-defined error class is the common case |
| **`self is skip_instance`** | — | walks off the constructor chain regardless of depth or file |

The middle one is what I wrote first, and `test_subclass_with_its_own_init_still_records_the_callers_line`
is the test that caught it — it defines `LayeredError` **inside the test function**, exactly the case
that breaks filename skipping.

🔧 **Why identity (`is`) and not `isinstance` or a name check:** `f_locals["self"]` on the constructor
frame *is* the object being built, the same object. Identity cannot be fooled by a subclass that
renames its parameter, and it will not falsely skip an unrelated method that happens to have a local
called `self`.

❓ **Why the plain `==` string compare instead of `Path(...).resolve()`:** verified — for a function
defined in this module, `co_filename` equals the module's `__file__` **exactly**:

```
module __file__  : C:\Bhavya\Medium\production_agentic_ai\app\core\error_context.py
func co_filename : C:\Bhavya\Medium\production_agentic_ai\app\core\error_context.py
```

`__file__` has been absolute since Python 3.9. No normalisation means no syscall and no exception to
guard — this function runs once per frame while walking a stack (§13 explains why that matters).

⚠️ **The limitation:** it skips *every* frame whose `self` is the exception, not only `__init__`. If
you ever give `AppException` a method that constructs diagnostics by calling `capture_origin` on
itself, that frame is skipped too. That is desirable today; it is also a surprise waiting for whoever
adds such a method.

---

## 18. `_exception_chain` — lines 184–203

```python
def _exception_chain(exc: BaseException) -> list[BaseException]:
    """`exc` plus the exceptions it was raised from, outermost first, bounded by `_MAX_CHAIN_DEPTH`.

    Follows `__cause__` (`raise X from e`) preferentially and falls back to `__context__` (an error
    raised while handling another). `__suppress_context__` is honoured, because `from None` is an
    explicit statement that the earlier error is not relevant.
    """
    chain: list[BaseException] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and len(chain) < _MAX_CHAIN_DEPTH and id(current) not in seen:
        chain.append(current)
        seen.add(id(current))
        if current.__cause__ is not None:
            current = current.__cause__
        elif not current.__suppress_context__:
            current = current.__context__
        else:
            current = None
    return chain
```

🔧 **Technical:** implements PEP 3134's three attributes. `__cause__` is explicit (`raise X from e`),
`__context__` is implicit (an exception raised inside an `except` block), and
`__suppress_context__` is set by `raise X from None`.

❓ **Why prefer `__cause__` over `__context__`:** `__cause__` is a deliberate statement of causality;
`__context__` is often coincidental — an error raised while cleaning up from another has a
`__context__` that is noise. When both exist, the explicit one is the one a developer chose to record.

❓ **What if we don't honour `__suppress_context__`:** `raise X from None` is the idiom for "the
earlier error is an implementation detail, do not report it" — used, for example, when translating a
library exception into a domain one and deliberately hiding the library. Ignoring it would print the
thing the author explicitly suppressed. Asserted by `test_suppressed_context_is_honoured`.

🚨 **The `seen` set is not paranoia — cycles are constructible and this hung without it.** Verified:

```python
a, b = ValueError("a"), ValueError("b")
a.__cause__ = b
b.__cause__ = a          # -> chain terminates at len=2
```

`__cause__` is a writable attribute, so a framework doing exception translation can create a cycle
by accident. Two guards (`_MAX_CHAIN_DEPTH` and `seen`) because they fail differently: the depth cap
bounds a long *legitimate* chain, the `seen` set catches a *cyclic* one that the depth cap would only
mask.

---

## 19. `first_party_frames` — lines 206–224

```python
def _walk(tb: TracebackType | None) -> list[CodeOrigin]:
    """Every frame of one traceback, outermost first (Python's own order)."""
    return [_origin_from_frame(frame, lineno) for frame, lineno in traceback.walk_tb(tb)]


def first_party_frames(exc: BaseException) -> list[CodeOrigin]:
    """Our own frames across the whole exception chain, **innermost first**.

    Innermost first is the reverse of Python's traceback order, and it is deliberate: the first entry
    is the line that broke, and each following entry is the caller that led there. That reads as a
    story ("failed in `invoke`, called from `chat`, called from the endpoint") and puts the most
    useful frame where the eye lands, instead of after 30 lines of framework.
    """
    ours: list[CodeOrigin] = []
    for link in _exception_chain(exc):
        for origin in reversed(_walk(link.__traceback__)):
            if origin.first_party and len(ours) < _MAX_FIRST_PARTY_FRAMES:
                ours.append(origin)
    return ours
```

🚨 **`reversed()` is the single most valuable character-for-character decision in these three files.**
Python's traceback is outermost-first, so the frame that actually broke is *last* — after 30 lines of
uvicorn and starlette. Reversing puts it **first**. Verified by
`test_blame_frame_points_at_the_deepest_line_of_our_own_code`, which asserts the exact order:

```python
    assert [f.function for f in frames[:4]] == [
        "_innermost_failure",
        "_middle_layer",
        "_outer_layer",
        "test_blame_frame_points_at_the_deepest_line_of_our_own_code",
    ]
```

That reads as a sentence: it broke in `_innermost_failure`, which was called from `_middle_layer`,
called from `_outer_layer`, called from the test.

❓ **Why filter to first-party at all — isn't the full traceback more complete?** The full traceback
*is* still logged, via `exc_info`. This list answers a different question: **which of my files do I
open?** Verified with `json.loads("{not json}")` — the exception is raised inside `json/decoder.py`,
and `test_blame_frame_skips_dependency_frames` asserts the blame frame is
`tests/test_exceptions.py`, your calling line. That is the useful answer; `json/decoder.py:353` is not.

⚠️ **The cap is checked inside the loop, so it truncates the *innermost* frames and drops outer
ones** — the right way round (nearest the failure is most useful), and the reason
`test_first_party_frames_are_capped` asserts `frames[0].function == "_recurse"` rather than only
checking the length.

---

## 20. `blame_frame` + `describe` — lines 227–275

```python
def _blame_from(ours: list[CodeOrigin], chain: list[BaseException]) -> CodeOrigin | None:
    """Pick the blame frame from an already-computed first-party list, or fall back.

    Takes the list rather than recomputing it, so `describe()` walks each traceback once instead of
    twice. See `_classify` for why a second walk is not free.
    """
    if ours:
        return ours[0]
    # Nothing of ours in the stack: a failure entirely inside a dependency still needs *a* location,
    # even if it is `httpx/_client.py`.
    for link in chain:
        frames = _walk(link.__traceback__)
        if frames:
            return frames[-1]
    return None
```

🚨 **`_blame_from` exists only because of finding #6.** `describe()` originally called
`blame_frame(exc)` *and* `first_party_frames(exc)`, each doing a full walk of every traceback in the
chain. Splitting the pure "pick one" logic out lets `describe()` walk once and pass the result to
both. `blame_frame()` survives as the public one-shot for callers who want only that.

```python
def describe(exc: BaseException) -> dict[str, Any]:
    """The full diagnostic bundle for one exception, ready to splat into a log call.

    Deliberately *only* the summary/index fields. The complete formatted traceback is attached
    separately by the caller via `exc_info`, so this dict stays small enough to keep in a log
    aggregator's indexed fields while the traceback lives in the message body.
    """
    chain = _exception_chain(exc)
    # One walk, reused for both the blame frame and the app_traceback list.
    ours = first_party_frames(exc)
    blame = _blame_from(ours, chain)
```

❓ **Why is every field conditional (`if blame is not None`, `if ours`, `if len(chain) > 1`):** so the
log line has no empty keys. A `"caused_by": []` on every single error is noise in every dashboard and
storage cost on every line; the key's *presence* is itself information ("this error was chained").
Verified — `describe(ValueError("never raised"))` returns exactly
`['exception_message', 'exception_module', 'exception_type']`, no `blame`, no `failed_at`. Asserted by
`test_describe_survives_an_exception_with_no_traceback`.

⚠️ **`describe()` deliberately does not include the traceback itself.** It stays small so an
aggregator can index every field; the traceback goes separately through `exc_info` and is rendered by
`dict_tracebacks` (see [`4_logging_guide.md`](./4_logging_guide.md) §8). Putting them in one dict
would push a multi-kilobyte string into your indexed fields.

---

## 21. `exception_handlers.py` docstring + config — lines 1–64

```python
# Status codes that mean "the caller made a mistake". They are logged at WARNING, not ERROR: a 404 is
# not a defect in this service, and paging on them trains people to ignore the alert.
_CLIENT_ERROR_CEILING = 500


@runtime_checkable
class ErrorDetailConfig(Protocol):
    """The only setting these handlers need: whether to put diagnostics in the response body.

    A one-field Protocol rather than `Settings`, for the same reason as `LoggingConfig` -- a test
    passes a stub and never touches `.env`. `Settings` satisfies it structurally.
    """

    DEBUG: bool
```

🔧 **One field.** Narrower than `logging.py`'s five-field `LoggingConfig`
([`4_logging_guide.md`](./4_logging_guide.md) §5), and the ISP point made as sharply as it gets: the
test stub is `@dataclass class FakeConfig: DEBUG: bool = False`.

❓ **Why a `_CLIENT_ERROR_CEILING` constant rather than `< 500` inline:** it appears in two handlers
(§25) and encodes a *policy* — "4xx is not our fault" — that someone might reasonably want to change.
A named constant makes it one edit and one grep.

⚠️ **It is imprecise and knowingly so:** a 3xx would also log at WARNING. No handler here can produce
a 3xx, so the simpler comparison wins over a range check.

---

## 22. `_request_id` — lines 67–74

```python
def _request_id() -> str | None:
    """The current request's id, as bound by `RequestContextMiddleware`.

    Read from structlog's contextvars rather than passed in, because the handler signature is fixed
    by FastAPI. Returning it to the client is what lets a user's screenshot be traced to a log line.
    """
    value = structlog.contextvars.get_contextvars().get("request_id")
    return str(value) if value is not None else None
```

❓ **Why read from contextvars instead of `request.state`:** FastAPI fixes the handler signature to
`(request, exc)`, and `request.state` would require middleware to write there *as well as* to
structlog's contextvars — two places holding the same id, which will diverge. The contextvar is
already the source of truth for every log line in the request.

🚨 **Verified across the middleware boundary.** The unhandled-exception handler runs in
`ServerErrorMiddleware`, which is **outside** `RequestContextMiddleware` (§28). The contextvars
survive because the middleware re-raises without clearing them, so the outer handler still sees the
id. Asserted by `test_error_id_and_request_id_correlate_response_to_log`, which checks the response
body's `request_id` equals the `X-Request-ID` header **and** the log line's `request_id`.

⚠️ **It returns `None` outside a request.** An `AppException` raised at startup (`config.py`'s guard)
has no request, so the envelope simply omits the key. The `str(value)` coercion is defensive — nothing
binds a non-string today.

---

## 23. `_log_error` — lines 77–85

Small function, and the discovery inside it is the one most likely to bite you elsewhere.

```python
def _log_error(event: str, exc: BaseException, *, level: str, **extra: Any) -> None:
    """The observability actor's line -- isolated so a log-format change never risks touching
    what is actually returned to a client.

    `exc_info=exc` is passed explicitly rather than relying on `logger.exception()`, because these
    handlers are `async` and the exception is an argument: there is no guarantee we are still inside
    the `except` block that `sys.exc_info()` would read from.
    """
    getattr(logger, level)(event, exc_info=exc, **describe(exc), **extra)
```

🚨 **`logger.exception()` here would log NO traceback at all.** This is the claim I most expected to
be over-cautious, and it is real. Starlette awaits the handler *after* the `except` block that caught
the exception has exited, so `sys.exc_info()` — which is what `logger.exception()` and `exc_info=True`
both read — is empty. Verified in an async handler receiving the exception as an argument:

```
sys.exc_info() inside the async handler = (None, None, None)
```

And end-to-end through the real pipeline, two log calls on the same exception:

| call | `exception` key in the JSON line |
|---|---|
| `log.error("...", exc_info=exc)` | **present** — full structured traceback |
| `log.error("...", exc_info=True)` | **absent** — keys were only `['event', 'level', 'logger', 'timestamp']` |

An `exc_info=True` line looks completely normal. It has a level, a message, a timestamp, and no
traceback — and you would not notice until the night you needed it.

❓ **Why `getattr(logger, level)` rather than an if/else:** the level is data (`"warning"` or
`"error"`, chosen per status code in §25), and `getattr` keeps it data. The alternative is a
two-branch conditional in three separate handlers.

⚠️ **`getattr` accepts any string**, so a typo like `level="warn"`... actually resolves (structlog
supports `warn`), but `level="wrn"` would raise `AttributeError` while handling an error. Both call
sites pass a literal, so the risk is bounded; a `Literal["warning", "error"]` annotation would close
it and was skipped as noise for two call sites.

> **The transferable idea:** `logger.exception()` is only correct **inside** the `except` block that
> caught the exception. Once the exception becomes a value you pass around — a handler argument, a
> queued job, a retry record — you must pass `exc_info=exc` explicitly, or you silently log no stack.

---

## 24. `_error_response` — lines 88–118

```python
    body: dict[str, Any] = {"error": error_code, "message": message}
    if error_id is not None:
        body["error_id"] = error_id
    request_id = _request_id()
    if request_id is not None:
        body["request_id"] = request_id
    if extra:
        body.update(extra)
    if debug is not None:
        # Sanitised, not passed through. A DEBUG response body is a second sink for the same
        # exception context that the log pipeline redacts, and it is the *more* exposed of the two:
        # developers paste HTTP responses into tickets and chat. Without this, an `AppException`
        # carrying `api_key=...` for debugging would render the live key verbatim in the response.
        body["debug"] = sanitise(debug)
    return JSONResponse(status_code=status_code, content=body)
```

🍕 **Plain terms:** the press office's single letterhead. Every statement, regardless of which
accident, comes out on the same paper with the same fields in the same order — so the recipient never
has to guess which format they got.

🚨 **`sanitise(debug)` is finding #5 — a security hole I introduced and then closed.** The
demonstration output, before the fix:

```json
"debug": {
  "api_key": "sk-live-SHOULD-NEVER-APPEAR",     ← the live key, in an HTTP response
  ...
}
```

while the *log line* for the same error correctly showed `"api_key": "***"`. The redaction policy
lived only inside a structlog processor, so it guarded exactly one sink. The fix was to extract
`sanitise()` in [`log_sanitizer.py`](../app/core/log_sanitizer.py) as the policy, leaving
`sanitise_event_dict` as a three-line structlog adapter over it. Asserted by
`test_debug_response_body_is_redacted`.

⚠️ **`DEBUG=true` is forbidden on staging and production tiers** by `config.py`'s startup guard
([`3_config_py_guide.md`](./3_config_py_guide.md) §15), so this could not have leaked in production.
It absolutely could have leaked in development — where, per this project's own `CLAUDE.md`, the `.env`
holds **live** API keys.

> **The transferable idea:** a redaction rule that guards one sink is a rule with a hole in it. Write
> the policy as a plain function and make every sink call it; the moment it exists only as a
> framework plugin, the next sink you add will bypass it.

---

## 25. `build_exception_handlers` — lines 121–213

```python
def build_exception_handlers(
    config: ErrorDetailConfig,
) -> dict[type[Exception], Any]:
```

🍕 **Plain terms:** a **switchboard**, wired once when the building opens. Four incoming lines, each
to the right desk, and the "do we give out internal detail?" policy set once at the switchboard
rather than re-decided by each desk.

❓ **Why a factory returning a dict, instead of four module-level functions:** three reasons.
`config.DEBUG` is read once and captured, so no handler consults a global (DIP). "Does this leak
internals in production?" becomes one testable question — construct with `DEBUG=False`, assert on the
bodies. And registration in `main.py` is a loop, so adding a handler is one row here and **zero**
lines in the app factory:

```python
    # One loop, not one call per type: adding a handler is a row in the registry (see
    # `build_exception_handlers`), so this factory never grows when a new failure family appears.
    for exception_type, handler in build_exception_handlers(settings).items():
        app.add_exception_handler(exception_type, handler)
```

### The registry, and why order does not matter

```python
    # The registry. Order is irrelevant -- Starlette dispatches on the most specific class in the
    # exception's MRO, not on insertion order.
    return {
        AppException: handle_app_exception,
        RequestValidationError: handle_validation_error,
        StarletteHTTPException: handle_http_exception,
        Exception: handle_unhandled_exception,
    }
```

🚨 **Verified, because this comment is load-bearing.** If dispatch *were* by insertion order, the
`Exception` entry would swallow everything. Test: register the catch-all **first**, then
`AppException`, and raise a subclass **two levels** below `AppException`:

```
DeepError MRO: ['DeepError', 'ConfigurationError', 'AppException', 'Exception', 'BaseException']
registered Exception first, AppException second -> ['AppException handler'], status=418
```

It reached the `AppException` handler and kept its own 418. This is what makes the "add a subclass,
never touch the handler" claim in §11 true rather than hopeful.

### Handler 1 — `handle_app_exception` (136–152)

```python
        # Client errors are the caller's fault and must not read as service defects; 5xx must.
        level = "warning" if exc.http_status_code < _CLIENT_ERROR_CEILING else "error"
        _log_error("app_exception", exc, level=level, **exc.log_context())
```

❓ **Why annotate `exc: AppException` rather than `exc: Exception` + `isinstance`:** the first version
had `assert isinstance(exc, AppException)` for type narrowing. Asserts are **compiled out under
`python -O`**, so it was a runtime check that vanishes in exactly the deployment that runs with
optimisations — and the registry already guarantees the type. The annotation narrows for mypy and
costs nothing at runtime. Verified: `uv run mypy app` reports no issues across 19 files.

Asserted by `test_client_error_app_exception_logs_at_warning_not_error`, which defines a 404 subclass
and checks the log line's level.

### Handler 2 — `handle_validation_error` (154–175)

```python
        errors = [
            {
                "field": ".".join(str(part) for part in error.get("loc", ())),
                "message": error.get("msg", ""),
                "type": error.get("type", ""),
            }
            for error in exc.errors()
        ]
```

🚨 **This handler exists because of finding #4.** FastAPI registers its own handlers for
`RequestValidationError` and `HTTPException` at app construction, **before** yours — verified:

```
HTTPException           -> fastapi.exception_handlers.http_exception_handler
RequestValidationError  -> fastapi.exception_handlers.request_validation_exception_handler
```

So without these two entries, a 422 answered `{"detail": [{"type": "int_parsing", "loc": [...]}]}`
while every other error answered `{"error", "message", "error_id"}`. A client cannot parse two shapes.

❓ **Why is `errors` forwarded to the client when §9 says context never is?** Because it describes the
**caller's own request**, not our internals — "which field was wrong" is the entire purpose of a 422,
and the caller already knows what they sent. `loc` is flattened from `["query", "n"]` to `"query.n"`
so the client gets a path it can use, verified by `test_validation_error_uses_the_shared_envelope`.

⚠️ **`.get("loc", ())` and `.get("msg", "")` rather than `[...]`** because `exc.errors()` is
pydantic's dict shape, and it has changed between pydantic v1 and v2. A `KeyError` here would turn a
client's bad input into a 500.

### Handler 3 — `handle_http_exception` (177–189)

```python
        level = "warning" if exc.status_code < _CLIENT_ERROR_CEILING else "error"
        _log_error("http_exception", exc, level=level, status_code=exc.status_code)
        return _error_response(
            status_code=exc.status_code,
            error_code=f"http_{exc.status_code}",
            message=str(exc.detail),
        )
```

❓ **Why `error_code=f"http_{exc.status_code}"`:** a Starlette `HTTPException` has no error code of its
own, and the envelope's contract is that `error` is always a stable machine-readable string. `http_404`
is derivable, greppable, and does not require inventing a taxonomy for framework errors. Asserted by
`test_not_found_uses_the_shared_envelope_and_logs_at_warning`.

⚠️ **No `error_id`** — an `HTTPException` is not an `AppException` and has none. The envelope omits
the key rather than fabricating one, which is why §24 makes `error_id` optional.

### Handler 4 — `handle_unhandled_exception` (191–204)

```python
        """The catch-all: anything not yet classified as an `AppException`.

        The response body is deliberately generic and carries no detail outside DEBUG -- an
        unclassified exception's message is the one most likely to contain a connection string, a
        row of data, or a provider's raw error text. The log line carries everything.
        """
        _log_error("unhandled_exception", exc, level="error")
```

❓ **Why is the message hardcoded to "An unexpected error occurred." instead of `str(exc)`:** because
an unclassified exception is by definition one nobody has vetted. `str(exc)` on a psycopg error is
your connection string; on an OpenAI error it is the provider's raw payload. A classified
`AppException` has a message its author chose to be client-safe — this one does not.

🎯 **Agentic AI angle:** this is the handler that will see the most traffic in an agent system,
because most failures come from *dependencies* — provider timeouts, tool errors, malformed model
output — none of which are yours to classify up front. That is precisely why the `blame_frame`
machinery matters: the log line still names **your** line in the call path, even though the exception
type belongs to `httpx`.

---

## 26. Measured performance

All from `uv run python scripts/bench_error_context.py` (Python 3.12.7, Windows).

### Before and after finding #6

| Operation | before | after | factor |
|---|---|---|---|
| `describe()`, 5-frame traceback | 9,138 µs | **10.7 µs** | 854× |
| `describe()`, 22-frame traceback | 40,284 µs | **39.1 µs** | 1,030× |
| `describe()`, 2-link cause chain | 11,588 µs | **21.6 µs** | 537× |
| `AppException("x")` construction | 628.8 µs | **5.3 µs** | 119× |
| `_classify`, cold → warm | 353 µs | **0.062 µs** | 5,670× |

### What it costs now

| Operation | cost | in context |
|---|---|---|
| `AppException` construction | 5.3 µs | vs `ValueError`'s 0.095 µs — **56× a bare exception** |
| `describe()` on a typical error | 10–40 µs | vs ~70 µs to render one log line |
| `describe()`, 62-frame traceback | 96.5 µs | the frame cap holds it here |

⚠️ **Accepted debt, written down:** an `AppException` is still 56× more expensive to construct than a
bare `Exception`, because `capture_origin` walks the stack. That is fine for an error path and **not**
fine for control flow — do not use `AppException` for expected, high-frequency conditions (a cache
miss, an empty result). **The trigger to revisit:** any code path constructing these in a loop.

---

## 27. What a real failure looks like

A three-layer agent stack — endpoint → `PortfolioAgent.summarise` → `LLMService.invoke` →
`OpenAIClient.complete` — where the provider drops the connection and the service wraps it.

**The HTTP response (production, `DEBUG=False`):**

```json
{
  "error": "llm_provider_unavailable",
  "message": "Upstream model provider is unavailable",
  "error_id": "102fad90e3b9",
  "request_id": "4be7166a-9700-4d3e-86cd-a0b6f8816e2e"
}
```

**The log line** (traceback elided; `service`/`version`/`env` come from the logging pipeline):

```json
{
  "exception_type": "LLMProviderError",
  "exception_message": "Upstream model provider is unavailable",
  "blame": {
    "file": "app/services/llm.py",
    "line": 50,
    "function": "LLMService.invoke",
    "module": "app.services.llm",
    "location": "app/services/llm.py:50 in LLMService.invoke"
  },
  "failed_at": "app/services/llm.py:50 in LLMService.invoke",
  "caused_by": ["ConnectionResetError: peer closed connection during TLS handshake"],
  "error_id": "102fad90e3b9",
  "error_code": "llm_provider_unavailable",
  "provider": "openai",
  "model": "gpt-5.4-mini",
  "attempt": 3,
  "api_key": "***",
  "hint": "check the provider status page before escalating",
  "raised_at": "app/services/llm.py:50 in LLMService.invoke",
  "request_id": "4be7166a-9700-4d3e-86cd-a0b6f8816e2e",
  "method": "GET",
  "path": "/summary",
  "level": "error"
}
```

Read the requirement off that: the **file**, the **line**, the **class**, the **method**, the
**underlying cause**, the agent-specific context (`provider`/`model`/`attempt`), the operator's next
step, the correlation ids — and the credential redacted. Plus the full two-link structured traceback
in the `exception` field.

**Log sequences per failure type**, verified end to end:

| Request | Events emitted | Response |
|---|---|---|
| classified `AppException` | `request_started` → **`app_exception`** → `request_finished` | 503 + envelope |
| unclassified exception | `request_started` → `request_failed` (no traceback) → **`unhandled_exception`** | 500 generic |
| bad query param | `request_started` → **`request_validation_failed`** (warning) → `request_finished` | 422 + `errors[]` |
| unknown route | `request_started` → **`http_exception`** (warning) → `request_finished` | 404 + envelope |

Note the second row: `request_finished` is **absent**, because the response never came back through
the middleware — which is exactly what §28 is about.

---

## 28. Middleware integration + the stack order

Starlette's real stack, read off `app.build_middleware_stack()`, outermost first:

```
starlette.middleware.errors.ServerErrorMiddleware      ← handles Exception (our catch-all)
  app.core.middleware.RequestContextMiddleware         ← ours: binds request_id, times the request
    starlette.middleware.exceptions.ExceptionMiddleware ← handles AppException, HTTPException, 422
      fastapi.middleware.asyncexitstack.AsyncExitStackMiddleware
        fastapi.routing.APIRouter                       ← your endpoint
```

🚨 **This ordering is finding #3, and it produced two tracebacks per failure.** Probed by instrumenting
a middleware and four handlers:

| Raised in the endpoint | What the middleware sees |
|---|---|
| `AppException` | `middleware:saw response 500` — the exception is converted **inside**, so middleware never sees it |
| `ValueError` | `middleware:caught ValueError` — then re-raised, then handled by `ServerErrorMiddleware` |

So an unclassified exception passes through **both** the middleware and the catch-all handler, and
the middleware's original `logger.exception("request_failed")` emitted a second full stack dump. One
failure looked like two incidents, at double the log volume.

```python
        except Exception as exc:
            duration_ms = (time.perf_counter() - start) * 1000
            # Deliberately NOT `logger.exception()`: this middleware sits *inside* Starlette's
            # ServerErrorMiddleware, so an escaping exception is logged again -- with the full
            # traceback and blame frame -- by `handle_unhandled_exception`. Emitting the traceback
            # here too produced two stack dumps per failure, which doubles log volume and makes a
            # single failure look like two. This line's job is only to close the request lifecycle
            # (its duration), so it records the type and leaves the diagnosis to the handler.
            logger.warning("request_failed", duration_ms=duration_ms, exception_type=type(exc).__qualname__)
            raise
```

Verified after the fix — of the three events emitted for a `ZeroDivisionError`, **exactly one**
carries a traceback:

```
events: ['request_started', 'request_failed', 'unhandled_exception']
events carrying a traceback: ['unhandled_exception']
```

❓ **Why keep `request_failed` at all?** It is the only line that records the request's **duration**
on the failure path — the handler does not know when the request started. Dropping it would mean
failed requests have no latency data, which is the half of your latency distribution you most want.

⚠️ **`app/core/middleware.py` is itself first-party**, so its re-raise frame appears in
`app_traceback` for unhandled exceptions, as the outermost entry. Harmless — it *is* in the call path —
and it is why a failure raised from outside the project root reports middleware as its blame frame
(§12).

---

## 29. SOLID scorecard

| Principle | How these files honour it |
|---|---|
| **S** — Single Responsibility | Four owners, four files: taxonomy (`exceptions.py`), stack reading (`error_context.py`), log+respond (`exception_handlers.py`), request lifecycle (`middleware.py`). An exception never logs; the introspector knows nothing of HTTP; the handler owns no failure semantics. |
| **O** — Open/Closed | New failure type = one subclass, two attribute overrides, **zero** handler changes (verified: a 2-level subclass dispatches correctly, §25). New handler = one row in the registry, zero lines in `create_app()`. |
| **L** — Liskov Substitution | `test_every_app_exception_subclass_honors_the_base_contract` parametrises over `__subclasses__()` **recursively**, so every subclass — including ones added later — is checked against the base contract the day it is written. |
| **I** — Interface Segregation | `ErrorDetailConfig` is a **one-field** Protocol (`DEBUG: bool`). `error_context.py` imports nothing from this project at all. |
| **D** — Dependency Inversion | `build_exception_handlers(config)` closes over the config; handlers depend on a captured value, not a global. `exceptions.py` depends on `capture_origin` (a function), not on a `StackInspector` class. |

### ⚠️ Where SOLID is deliberately NOT applied

**No `ErrorReporter` interface with a `LogErrorReporter` implementation.** `_log_error` and
`_error_response` are module-level functions. There is one log sink and one response format; an
interface with one implementation is indirection that substitutes nothing. If a second sink appears
(Sentry, an audit table), the seam is `_log_error`'s body, not a new hierarchy.

**No `ExceptionMapper` class.** The mapping from exception type to handler is a **dict**, and the
mapping from exception to status code is a **class attribute**. Both are data. A mapper class would
wrap a dict lookup in a method call and add a lifecycle to manage.

**`CodeOrigin` is a frozen dataclass, not a class with behaviour.** It has one property and one
serialiser and no invariants to protect beyond immutability.

**Handlers are closures, not a `Handler` base class with four subclasses.** Four subclasses would
mean four files' worth of ceremony to express what four `async def`s express directly, and they would
each need the config injected separately — which is the thing the closure does for free.

> **The transferable idea:** the seams here are the **registry** (data), the **Protocol** (a stub in
> tests), and the **factory** (config captured once). Three seams, each with something concrete
> plugging into it. Every abstraction I did not write would have had exactly one implementation
> forever.

---

## 30. Where this fits in the 7 layers

```
                          an exception is raised, anywhere
                                      │
              ┌───────────────────────┴────────────────────────┐
              ▼                                               ▼
   ┌──────────────────────┐                       ┌────────────────────────┐
   │   exceptions.py      │                       │  a dependency's error  │
   │  AppException(...)   │                       │  httpx / openai / db   │
   │  ├ error_id          │                       │  (no error_id, no      │
   │  ├ context {…}       │                       │   origin, not ours)    │
   │  └ origin  ◄─────────┼── capture_origin()    └───────────┬────────────┘
   └──────────┬───────────┘   (error_context.py)              │
              │                                              │
              └──────────────────┬───────────────────────────┘
                                 ▼
                   ┌─────────────────────────────┐
                   │     error_context.py        │
                   │  _exception_chain  (cause)  │
                   │  first_party_frames (ours)  │
                   │  blame_frame  → THE LINE    │
                   │  describe()  → flat fields  │
                   └──────────────┬──────────────┘
                                  ▼
                   ┌─────────────────────────────┐
                   │   exception_handlers.py     │
                   │   registry → 4 handlers     │
                   └───────┬─────────────┬───────┘
                           ▼             ▼
                 _log_error()      _error_response()
                       │                   │
                       ▼                   ▼
            logging.py pipeline      JSON envelope
            (redacted, L6)           error + message
                       │              + error_id
                       ▼              + request_id
              stdout → aggregator     + debug (DEBUG only,
                                        also redacted)
```

**Why this is Layer 0 infrastructure serving Layer 6:** every layer raises, so the error path cannot
live inside any one of them. `exceptions.py` and `error_context.py` sit next to
[`config.py`](../app/core/config.py) with almost no dependencies; `exception_handlers.py` is the one
piece that knows about HTTP.

| Ordinary web service | Agentic AI system |
|---|---|
| Most errors are yours (a bug, a bad query) | Most errors are **dependencies'** — provider timeouts, tool failures, malformed model output — so the catch-all handler is the busy one |
| A traceback names your file near the top | Your frame is buried under langchain/httpx/ssl; **`blame_frame` is the only thing that finds it** |
| Error context is scalars (user id, status) | Error context is `provider`/`model`/`attempt`/`prompt_tokens` — and prompts, which are unbounded and may hold PII |
| Failure is loud: a 500 you can alert on | Failure is often *degradation* — the agent answers, badly. The log line is the only signal |
| One error per failed request | One request retries a provider 3× across 12 tool calls: **many** errors, so a 40 ms diagnostic cost compounds (§26) |
| Stack depth ~10 frames | 40+ frames, and re-entrant agent loops can go deeper still (hence the frame cap) |

---

## 31. How to extend it

### Add a failure type (the common case)

```python
class RateLimitError(AppException):
    """Raised when a caller exceeds their quota."""

    error_code = "rate_limit_exceeded"
    http_status_code = 429
```

That is all. It logs at WARNING automatically (429 < 500), dispatches to `handle_app_exception`
without a registry change, and is picked up by the LSP contract test the moment it exists.

### Let one context field reach the client

```python
class ValidationError(AppException):
    error_code = "validation_error"
    http_status_code = 422

    def client_payload(self) -> dict[str, Any]:
        return {**super().client_payload(), "field": self.context.get("field")}
```

Overriding on the exception makes the exposure a visible, reviewable line **at the definition** — not
a handler that a future edit could widen for everything.

### Add a second error sink (Sentry, an audit table)

Extend `_log_error`'s body. It is the single place every error path funnels through:

```python
def _log_error(event: str, exc: BaseException, *, level: str, **extra: Any) -> None:
    getattr(logger, level)(event, exc_info=exc, **describe(exc), **extra)
    if level == "error":
        sentry_sdk.capture_exception(exc)      # one line, four handlers covered
```

### Wrap a third-party exception

```python
try:
    return await self._client.complete(prompt)
except httpx.TimeoutException as exc:
    raise LLMProviderError("provider timed out", provider="openai", attempt=n) from exc
```

`from exc` is what populates `caused_by` and keeps the dependency's frames in the chain (§18) — while
`blame_frame` still reports **your** line.

### What is deliberately NOT built

| Not built | Why | Trigger |
|---|---|---|
| A failure taxonomy (`NotFoundError`, `ToolError`, …) | Scaffolding for layers that do not exist; each needs a status code and redaction decision made with real calling code in front of you | add each in the commit that first raises it |
| `AppException.wrap(exc)` | `raise X from exc` already does it in one line | a repeated 5-line wrapping pattern across services |
| `retryable: bool` on the envelope | No client consumes it yet | the first client that implements retry logic |
| OpenTelemetry `span.record_exception` | No spans exist yet; the hook is one line in `_log_error` | first distributed trace |
| Content-based PII detection in error context | Key-name matching is deterministic; content matching needs a classifier and produces false positives | a compliance rule naming content, not fields |
| `Literal["warning", "error"]` on `_log_error`'s level | Two call sites, both literals | a third caller, or a typo that reaches production |

---

## 32. Cheat sheet

```
RAISE
  classified       raise ConfigurationError("bad config", field="LOG_LEVEL", hint="check .env")
  wrapping         raise LLMProviderError("provider down", provider="openai") from exc
  new type         class RateLimitError(AppException): error_code=...; http_status_code=429
  hint is kw-only  ConfigurationError("m", "h")  -> TypeError

THREE LOCATION LAYERS (all in every error log line)
  raised_at      where the AppException was CONSTRUCTED      (exceptions.py, capture_origin)
  failed_at      deepest FIRST-PARTY traceback frame         (error_context.py, blame_frame)
  app_traceback  our frames, INNERMOST FIRST                 (error_context.py)
  exc_info       the full chained traceback                  (rendered by dict_tracebacks)

THREE AUDIENCES, THREE METHODS
  log_context()    error_id, error_code, message, **context, hint, raised_at   -> logs only
  client_payload() error, message, error_id                                   -> anyone
  debug_payload()  log_context() + exception + structured raised_at            -> DEBUG only, SANITISED

RESPONSE ENVELOPE (one shape, every error path)
  { error, message, error_id?, request_id?, errors?[422], debug?[DEBUG only] }
  error_id    12 hex, in BOTH response and log -> the correlation key
  request_id  from structlog contextvars, == X-Request-ID header

FOUR HANDLERS (registry order is irrelevant — Starlette dispatches on MRO)
  AppException            -> app_exception            level from http_status_code
  RequestValidationError  -> request_validation_failed 422, warning, errors[] to client
  StarletteHTTPException  -> http_exception            error_code = http_<status>
  Exception               -> unhandled_exception       500, generic message, nothing leaked

MEASURED (py3.12.7 / scripts/bench_error_context.py)
  AppException()    5.3 us   (vs ValueError 0.095 us — 56x; do NOT use for control flow)
  describe()       10-40 us  typical; 96 us at the 62-frame cap
  _classify warm   0.062 us  (cold 353 us — the lru_cache is load-bearing, not an optimisation)
  caps             _MAX_FIRST_PARTY_FRAMES=15   _MAX_CHAIN_DEPTH=5

NEVER
  x logger.exception(...) in an async handler   sys.exc_info() is EMPTY -> logs NO traceback
  x exc_info=True with the exception as an arg  same bug, looks like a normal log line
  x logging inside AppException.__init__        an exception is a value, not an event
  x str(exc) in a client response               unclassified messages hold DSNs and provider payloads
  x self.context reaching client_payload()      override on the subclass instead, deliberately
  x a debug body without sanitise()             a response is the MORE exposed sink than a log
  x sys._getframe(N) to find a raise site       every subclass __init__ shifts N
  x skipping frames by filename                 breaks when the subclass shares the caller's file
  x assert isinstance(...) for narrowing        compiled out under python -O
  x logger.exception in middleware              double traceback: it re-raises into ServerErrorMiddleware
  x AppException for expected conditions        56x a bare exception; use a return value
```

### Verification commands

```bash
uv run pytest tests/test_exceptions.py -q          # 30 tests
uv run pytest -q                                   # 82 tests, app/ at 99.55% coverage
uv run ruff check . && uv run ruff format --check .
uv run mypy app                                    # clean, 19 files
PYTHONPATH=. uv run python scripts/bench_error_context.py

# see a real failure end to end
LOG_FORMAT=json uv run python -c "
from app.core.config import get_settings
from app.core.error_context import describe
from app.core.exceptions import ConfigurationError
from app.core.logging import configure_logging, get_logger
configure_logging(get_settings())
try:
    raise ConfigurationError('demo', api_key='sk-LEAK', hint='look here')
except ConfigurationError as exc:
    get_logger('demo').error('app_exception', exc_info=exc, **describe(exc), **exc.log_context())"
```

---

## 📎 Related files

| File | Relationship |
|---|---|
| [`app/core/logging.py`](../app/core/logging.py) | the pipeline these log lines travel — see [`4_logging_guide.md`](./4_logging_guide.md) |
| [`app/core/log_sanitizer.py`](../app/core/log_sanitizer.py) | `sanitise()` guards both the log line **and** the DEBUG response body (§24) |
| [`app/core/config.py`](../app/core/config.py) | raises `ConfigurationError`; supplies `DEBUG` — see [`3_config_py_guide.md`](./3_config_py_guide.md) |
| [`app/core/middleware.py`](../app/core/middleware.py) | binds `request_id`; the double-logging fix lives here (§28) |
| [`app/main.py`](../app/main.py) | installs the registry in one loop |
| [`tests/test_exceptions.py`](../tests/test_exceptions.py) | 30 tests; every claim here is asserted there |
| [`scripts/bench_error_context.py`](../scripts/bench_error_context.py) | reproduces every number in §26 |

---

*Last updated: 2026-08-19 | Based on `app/core/exceptions.py` (112 lines), `app/core/error_context.py` (275 lines) and `app/core/exception_handlers.py` (213 lines) of the `production_agentic_ai` project*
