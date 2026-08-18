# 🪵 `app/core/logging.py` + `app/core/log_sanitizer.py` — Line-by-Line Guide

> **Purpose:** A personal reference covering **every line** of this project's logging pipeline —
> both files, because they are one design split across two owners. For each line: what it means in
> plain English, **what breaks if you don't write it**, the technical mechanism, why *this* way and
> not the obvious alternatives, and where it fits in a production agentic AI system.
>
> **Written:** 2026-08-19, after replacing the article's `structlog` setup and then discovering that
> **four of the justifications written into the new code were factually wrong.** Those corrections
> are the most valuable part of this guide — see the callout below.
> **Companion docs:** [`3_config_py_guide.md`](./3_config_py_guide.md) explains where `LOG_LEVEL`
> and `LOG_FORMAT` come from. [`1_env_guide.md`](./1_env_guide.md) explains what each env var means.
> This guide explains *what happens to a log line between your call site and stdout*.

---

## 🚨 Read this first — five beliefs that verification destroyed

Every one of these was written in a code comment as settled fact, then disproved by running it.
They are listed first because **future-you will re-derive the wrong version otherwise.**

| # | The belief | What actually happens | Consequence |
|---|---|---|---|
| 1 | `cache_logger_on_first_use=True` breaks `structlog.testing.capture_logs()` | **False since structlog 25.5.** `capture_logs()` mutates the configured processor list *in place*, with a source comment saying it does so "to not break references held by bound loggers". Caching and `capture_logs` coexist fine. | The comment inherited from the previous `logging.py` was **stale**, repeating pre-25.5 behaviour. Deleted. |
| 2 | …so caching is safe to enable | **Also false, for a different reason.** `configure_logging()` builds a *brand-new* processors list. With caching on, a logger already used keeps the **old** list — a re-configure is silently ignored (probe logger still stamped `service: "first"` after being reconfigured to `"second"`). | Caching stays **off**, but the honest reason is *reconfiguration*, not tests-capture. |
| 3 | `CallsiteParameterAdder` is the most expensive processor in the chain | **False.** `sanitise_event_dict` is: **11.65 µs** vs callsite's **4.61 µs** on a flat event; **38.10 µs** vs **4.84 µs** on a nested agent payload. | The decision to gate callsite still holds (it adds **41%** to a full line) — but on measured overhead, not on a false ranking. |
| 4 | Pre-formatting exceptions with `format_exc_info` ruins `ConsoleRenderer`'s pretty traceback | **Not by itself.** With `rich` absent — and it *is* absent here — both paths render **byte-identical** output. The gain is conditional on installing `rich`. | Comment softened to say the benefit is conditional. The *real*, unconditional difference is on the JSON side (§8). |
| 5 | `LoggingConfig` is a 2-field Protocol | Stale in [`3_config_py_guide.md`](./3_config_py_guide.md) — it is now **5 fields** (`LOG_LEVEL`, `LOG_FORMAT`, `PROJECT_NAME`, `VERSION`, `APP_ENV`). | Guide 3 corrected. |

**The meta-lesson:** a comment explaining *why* is a claim about behaviour, and claims rot. Comment
#1 was true when someone wrote it and false by the time it was inherited — and nothing failed,
because nothing tested the *reason*. **Benchmark the thing you are about to justify by performance,
and re-run the thing you are about to justify by library behaviour.** Otherwise you are writing
folklore with syntax highlighting.

---

## 📚 Table of Contents

| § | Section | File | Lines |
|---|---|---|---|
| 1 | [What these two files are](#1-what-these-two-files-are) | both | — |
| 2 | [Why it is two files and not one](#2-why-it-is-two-files-and-not-one) | both | — |
| 3 | [Module docstring — the contract](#3-module-docstring--lines-123) | `logging.py` | 1–23 |
| 4 | [Imports](#4-imports--lines-2534) | `logging.py` | 25–34 |
| 5 | [`LoggingConfig` Protocol](#5-loggingconfig--lines-3749) | `logging.py` | 37–49 |
| 6 | [`_MANAGED_LOGGERS` — the uvicorn takeover](#6-_managed_loggers--lines-5465) | `logging.py` | 54–65 |
| 7 | [`_CALLSITE_PARAMETERS`](#7-_callsite_parameters--lines-6774) | `logging.py` | 67–74 |
| 8 | [`_TAIL_PROCESSORS` + `_tail_processors_for`](#8-_tail_processors--lines-7797) | `logging.py` | 77–97 |
| 9 | [`_wants_callsite` — the 41% decision](#9-_wants_callsite--lines-100109) | `logging.py` | 100–109 |
| 10 | [`_service_fields` — the closure](#10-_service_fields--lines-112128) | `logging.py` | 112–128 |
| 11 | [`_shared_processors` — chain order](#11-_shared_processors--lines-131152) | `logging.py` | 131–152 |
| 12 | [`configure_logging` — the whole wiring](#12-configure_logging--lines-155216) | `logging.py` | 155–216 |
| 13 | [`_take_over_managed_loggers`](#13-_take_over_managed_loggers--lines-219233) | `logging.py` | 219–233 |
| 14 | [`get_logger`](#14-get_logger--lines-236238) | `logging.py` | 236–238 |
| 15 | [Sanitizer docstring — the second owner](#15-sanitizer-docstring--lines-112) | `log_sanitizer.py` | 1–12 |
| 16 | [The deny-lists and the caps](#16-the-deny-lists-and-the-caps--lines-2285) | `log_sanitizer.py` | 22–85 |
| 17 | [The traversal](#17-the-traversal--lines-88137) | `log_sanitizer.py` | 88–137 |
| 18 | [`sanitise` + `sanitise_event_dict` — the entry points](#18-sanitise--sanitise_event_dict--lines-140166) | `log_sanitizer.py` | 140–166 |
| 19 | [Measured performance](#19-measured-performance) | both | — |
| 20 | [SOLID scorecard](#20-solid-scorecard) | both | — |
| 21 | [Where this fits in the 7 layers](#21-where-this-fits-in-the-7-layers) | both | — |
| 22 | [How to extend it](#22-how-to-extend-it) | both | — |
| 23 | [Cheat sheet](#23-cheat-sheet) | both | — |

---

## 1. What these two files are

🍕 **Plain terms:** a **newspaper printing press with a censor at the end of the line.**

`logging.py` is the press. Every department in the building (your code, uvicorn, httpx, LangChain)
files stories in its own format, and the press's job is to make them all come out in **one
consistent layout** — same date stamp, same masthead, same column structure — so a reader can scan
the whole paper without re-learning the format on every page.

`log_sanitizer.py` is the censor standing at the last station before the paper is printed. It reads
every field of every story and asks two questions: *is this allowed to leave the building?* and *is
this short enough to fit on the page?* Nothing reaches print without passing that desk — including
stories filed by departments that don't know the censor exists.

🔧 **Technical:** together they configure one `structlog` processor pipeline and one stdlib
`logging` handler, wired through `structlog.stdlib.ProcessorFormatter`, so both structlog calls and
foreign stdlib records render through the same processors to the same JSON (or console) stream on
stdout — with credential redaction and value-size capping applied as the final processor.

### The one idea behind both files

> **One shape, one stream, nothing sensitive, nothing unbounded.**

Every decision below traces to that sentence. *One shape* is why `ProcessorFormatter` exists and why
uvicorn's handlers get destroyed. *One stream* is why there is no file handler. *Nothing sensitive*
and *nothing unbounded* are the sanitizer, and they are the only two rules allowed to reject data
that a call site deliberately passed.

---

## 2. Why it is two files and not one

The split is by **who asks for the change**, which is the only definition of Single Responsibility
that survives contact with a real codebase:

| Change request | Lands in | Comes from |
|---|---|---|
| "Ship to Datadog instead of stdout" | `logging.py` | platform / SRE |
| "Add `trace_id` to every line" | `logging.py` | observability |
| "Stop logging uvicorn's access lines" | `logging.py` | cost / noise review |
| "You're leaking the JWT in tool-call logs" | `log_sanitizer.py` | security |
| "Client SSNs must never appear in logs" | `log_sanitizer.py` | compliance / audit |

Those two columns are different people on different days, and the second column is the one that gets
**audited**. Keeping them apart means a security reviewer opens a 154-line file that is almost
entirely a deny-list, instead of a file where a credential rule sits next to `structlog.configure()`
plumbing they must not touch.

❓ **Why not split the sanitizer further?** It does two jobs — redact secrets *and* cap sizes — which
strictly is two responsibilities. They are together because both are decided **per leaf value during
one traversal** of a possibly-deep event dict. Two processors means crawling a nested LangChain
payload twice; measured, that walk is already the most expensive step in the chain (§19), so doubling
it would be the single worst change you could make to this pipeline.

⚠️ **The coupling this creates:** `logging.py` imports `sanitise_event_dict` and appends it last
(line 151). That single line is the entire contract. `logging.py` never learns *what* is redacted;
the sanitizer never learns whether output is JSON or console. If you ever need the sanitizer to
behave differently per format, that is the seam that has to change — and it should become a
processor *factory*, not a flag inside the sanitizer.

> **The transferable idea:** split files by **who files the bug report**, not by what the code looks
> like. Two functions that always change together belong in one file even when a textbook says
> otherwise; two constants that answer to different reviewers belong apart even when they are three
> lines each.

---

## 3. Module docstring — lines 1–23

```python
"""Structured logging pipeline, configured once at process start.

**One pipeline for the whole process.** Our own calls (via structlog) and every dependency's calls
(uvicorn, httpx, LangChain, via stdlib `logging`) are rendered by the same `ProcessorFormatter`, so
a production log stream has exactly one shape. Without that, uvicorn keeps its own handlers and the
stream comes out half JSON and half plain text -- the failure mode that makes a log aggregator
useless precisely when you need it.
```

🔧 **Technical:** the docstring documents four things because they are the four a reader would
otherwise reverse-engineer: the one-pipeline guarantee, the no-files decision, the four extension
points, and the Protocol-not-Settings dependency.

❓ **Why document "output goes to stdout only, never to files":** because it is the decision most
likely to be "helpfully" undone. The article's version wrote a `.jsonl` file per day, and it looks
like a feature. It is a bug factory: an `open()`/`write()`/`close()` **per log line**, no rotation,
and a path computed once at startup so the "daily" file never actually rolls over. The platform
(Docker's log driver, systemd, the k8s node agent) already does rotation and shipping correctly.

⚠️ **Known limitation, stated on purpose:** stdout-only means **if nothing captures stdout, logs are
gone.** That is correct for containers and wrong for someone running `python -m app` on a VM and
closing the terminal. The trigger for revisiting is a deployment target that is not a container.

---

## 4. Imports — lines 25–34

```python
from __future__ import annotations

import logging
import sys
from typing import Protocol, runtime_checkable

import structlog

from app.core.exceptions import ConfigurationError
from app.core.log_sanitizer import sanitise_event_dict
```

| Import | Why it's here |
|---|---|
| `from __future__ import annotations` | lets `dict[str, int \| None]` (line 54) work as an annotation without runtime cost |
| `import logging` | **this file is named `logging.py`** and still imports stdlib `logging` |
| `sys` | exactly one use: `sys.stdout` at line 194 |
| `Protocol, runtime_checkable` | the ISP boundary, §5 |
| `ConfigurationError` | raised by `_tail_processors_for`; the same exception config's guard raises |
| `sanitise_event_dict` | the *only* thing imported from the sanitizer — the whole coupling |

🚨 **The name collision that doesn't bite.** `app/core/logging.py` doing `import logging` resolves to
**stdlib** `logging`, not itself, because Python 3 has only absolute imports (PEP 328). Under Python
2 this file would be unbuildable. Verified by the fact that the app boots at all.

⚠️ **The trap it does cause:** anywhere else in the codebase, `import logging` inside a module that
also does `from app.core import logging` will confuse a reader long before it confuses the
interpreter. The convention that avoids it: always `from app.core.logging import get_logger`, never
`from app.core import logging`.

---

## 5. `LoggingConfig` — lines 37–49

```python
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
```

🍕 **Plain terms:** a job advert, not a hiring contract. It says "I need someone who can tell me five
things." Anything that can answer those five gets the job — no interview, no paperwork, no
inheriting from a base class.

🔧 **Technical:** PEP 544 structural subtyping. `Settings` (from
[`config.py`](../app/core/config.py)) never mentions `LoggingConfig` and never imports it, yet
satisfies it. `@runtime_checkable` additionally permits `isinstance(x, LoggingConfig)` — which
checks *attribute presence only*, not types.

❓ **What if we don't write it:** `configure_logging(settings: Settings)` would import `Settings`,
which reads `.env` files at construction. Every logging test would then need a real environment.
`FakeConfig` in [`tests/test_logging.py`](../tests/test_logging.py) is a 5-field `@dataclass` — that
is only possible because of this Protocol.

🚨 **This grew from 2 fields to 5, and that is a real cost, not a free change.** Guide 3 still called
it a "2-field Protocol" (now corrected). Each field added here widens what a stub must provide, and
`PROJECT_NAME`/`VERSION`/`APP_ENV` are needed **only** to stamp service identity (§10). The
alternative — passing a separate `service_name: str` argument — was rejected because it moves the
same three values to every call site instead of one Protocol. But the honest framing is: this
Protocol is now a *narrow view*, not a *minimal* one.

---

## 6. `_MANAGED_LOGGERS` — lines 54–65

```python
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
```

🍕 **Plain terms:** the list of departments that were **running their own printing press in the
basement**. You don't ask them to match the house style — you take their press away and make them
file through yours.

🔧 **Technical:** each key is a stdlib logger whose handlers get destroyed and whose `propagate` is
forced `True` by §13. The value is the level to pin, or `None` to inherit root's.

🚨 **This exists because of a verified fact about uvicorn.** Read straight out of
`uvicorn.config.LOGGING_CONFIG`:

```
uvicorn        -> {'handlers': ['default'], 'level': 'INFO', 'propagate': False}
uvicorn.error  -> {'level': 'INFO'}
uvicorn.access -> {'handlers': ['access'], 'level': 'INFO', 'propagate': False}
```

And after `dictConfig` applies it (which uvicorn does in `Config.load()`, **before** it imports your
app):

```
uvicorn:        handlers=[<StreamHandler <stderr>>]  propagate=False  level=20
uvicorn.access: handlers=[<StreamHandler <stdout>>]  propagate=False  level=20
```

❓ **What if we don't write it:** `propagate=False` means those records **never reach the root
handler**. Your own lines come out as JSON; uvicorn's startup banner and access log come out as
plain text on a different stream. Your aggregator ingests half a schema. This is invisible in
development (where you're reading with your eyes) and only shows up when you try to query
production.

❓ **Why is `uvicorn.access` suppressed rather than reformatted?** Because
[`middleware.py`](../app/core/middleware.py) already emits `request_finished` with `request_id`,
`method`, `path`, `status_code` **and** `duration_ms`. uvicorn's access line has no request_id and
no duration you can correlate. Keeping both means paying twice to store a strict subset.

⚠️ **Known trap:** this dict is a **maintenance coupling with your dependency list.** `httpx` and
`httpcore` are here because LangChain's OpenAI client uses them. Add a dependency that logs
chattily at INFO and nothing warns you — you find out from your log bill. The signal to watch: any
single `logger` value dominating a volume-by-logger query.

🎯 **Agentic AI angle:** in an ordinary web app, one request produces one outbound call, so httpx's
INFO line roughly doubles your log volume. An agent doing 12 tool calls and 4 LLM round-trips per
request produces **16 httpx lines per user action** — the dependency out-logs your application by an
order of magnitude, and none of those lines carry the reasoning context you'd actually debug with.

---

## 7. `_CALLSITE_PARAMETERS` — lines 67–74

```python
# Cheap to add, expensive to render: each of these makes `CallsiteParameterAdder` walk the stack.
_CALLSITE_PARAMETERS = frozenset(
    {
        structlog.processors.CallsiteParameter.FILENAME,
        structlog.processors.CallsiteParameter.FUNC_NAME,
        structlog.processors.CallsiteParameter.LINENO,
    }
)
```

🔧 **Technical:** the set given to `CallsiteParameterAdder`, which resolves them via stack
inspection (`sys._getframe` walking) per event.

❓ **Why only three, when structlog offers `MODULE`, `PATHNAME`, `PROCESS`, `THREAD` and more:** the
article's version requested five including `PATHNAME`, which duplicates `FILENAME` with an absolute
path — the same information, plus your build machine's directory layout, on every line. `MODULE`
duplicates what `add_logger_name` already provides for free.

⚠️ **Deliberate stopping point:** `frozenset` (not `set`) because it is module-level shared state.
Mutating it at runtime would change the behaviour of every subsequent `configure_logging()` call.

---

## 8. `_TAIL_PROCESSORS` — lines 77–97

```python
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
```

🍕 **Plain terms:** the shelf of **output trays**. Ask for `json`, you get the tray that produces
machine-readable pages. Ask for `console`, you get the human-readable tray. Ask for `yaml`, the
building refuses to open rather than quietly using the wrong tray.

🔧 **Technical:** a dict from `LOG_FORMAT` to the tuple of processors passed as
`ProcessorFormatter(processors=[remove_processors_meta, *tail])` at line 191.

🚨 **This is where belief #4 broke.** The comment originally claimed pre-formatting with
`format_exc_info` *disables* ConsoleRenderer's rich traceback. Measured, with `rich` not installed:

```
--- ConsoleRenderer AFTER format_exc_info ---     --- ConsoleRenderer with raw exc_info ---
it_broke                                          it_broke
Traceback (most recent call last):                Traceback (most recent call last):
  File "...verify_logging.py", line 89              File "...verify_logging.py", line 89
    raise ValueError("boom")                          raise ValueError("boom")
ValueError: boom                                  ValueError: boom
```

**Byte-identical.** The claim only holds if `rich` is installed, and it is not a dependency here.

❓ **So why keep the split?** Because the **JSON** difference is real and unconditional:

```
format_exc_info -> exception is str
dict_tracebacks -> exception is list, keys = ['exc_notes', 'exc_type', 'exc_value',
                   'exceptions', 'frames', 'is_cause', 'is_group', 'syntax_error']
```

A flat string forces your aggregator into substring matching. A list of frames lets you build
`count by exc_type` and alert on a specific raising function. Asserted by
`test_exception_is_rendered_as_a_structured_traceback`.

❓ **Why a dict and not `if log_format == "json": ... else: ...`:** adding `logfmt` is then one row
instead of a new branch inside `configure_logging`. The lookup *is* the decision (OCP).

```python
def _tail_processors_for(log_format: str) -> tuple[structlog.types.Processor, ...]:
    """Look up the rendering chain for a LOG_FORMAT value; unknown values fail loud, not silently."""
    try:
        return _TAIL_PROCESSORS[log_format]
    except KeyError as exc:
        raise ConfigurationError(
            f"Unknown LOG_FORMAT: {log_format!r}", valid_formats=sorted(_TAIL_PROCESSORS)
        ) from exc
```

❓ **What if we don't write the raise:** `LOG_FORMAT=jsonl` (a plausible typo) would `KeyError` deep
inside `configure_logging` with no hint of the valid values. Verified output:

```
{'error_code': 'configuration_error', 'message': "Unknown LOG_FORMAT: 'yaml'",
 'valid_formats': ['console', 'json']}
```

The error **lists the valid values by reading the registry**, so it can never drift out of date.
Asserted by `test_unknown_log_format_fails_loudly`.

⚠️ **The consequence of owning validation here:** `config.py` deliberately does *not* validate
`LOG_FORMAT` (its comment at line 144 says so), so a bad value fails at `configure_logging()` rather
than at `Settings()` construction. That is microseconds later in the same startup path — acceptable —
but it does mean `Settings` can hold a `LOG_FORMAT` that will never render.

---

## 9. `_wants_callsite` — lines 100–109

```python
def _wants_callsite(config: LoggingConfig) -> bool:
    """Whether to pay for file/function/line on every line.

    `CallsiteParameterAdder` walks the stack per event. Measured on this chain it costs ~30 us of a
    ~74 us log line -- about 41% overhead -- and in an agentic system log volume scales with tool
    calls and streamed steps, not with requests. So it is on where a human is reading the output
    (console) or has explicitly asked for detail (DEBUG), and off otherwise, where `logger` +
    `event` already say where a line came from and any error carries a full structured traceback.
    """
    return config.LOG_FORMAT == "console" or config.LOG_LEVEL == "DEBUG"
```

🚨 **This docstring's original version was belief #3 and it was wrong.** It said callsite was "the
most expensive processor in the chain." Measured, per call, on a realistic 7-field agent event:

| Processor | µs/call (flat) | µs/call (nested payload) |
|---|---|---|
| `sanitise_event_dict` | **11.65** | **38.10** |
| `JSONRenderer` | 4.71 | — |
| `CallsiteParameterAdder` | 4.61 | 4.84 |
| `TimeStamper(iso, utc)` | 2.79 | — |
| `UnicodeDecoder` | 0.76 | — |
| `StackInfoRenderer` | 0.41 | — |
| `merge_contextvars` | 0.37 | — |
| `add_log_level` | 0.23 | — |

Callsite is **third**. The sanitizer is 2.5× more expensive flat and 8× more expensive on nested
data — and it *cannot* be gated, because it is the security guarantee.

❓ **So does the decision survive?** Yes, on the end-to-end number rather than the ranking:

```
LOG_LEVEL=INFO    73.62 us/line   (production default, callsite OFF)
LOG_LEVEL=DEBUG  103.55 us/line   (callsite ON)
-> callsite adds 29.94 us/line (41% overhead)
```

41% of every line, forever, for information you can usually get from `logger` + `event`. Gating it
is right; the reasoning just had to be rebuilt on real numbers.

❓ **Why `LOG_FORMAT == "console" or LOG_LEVEL == "DEBUG"` rather than a dedicated setting:** a
`LOG_CALLSITE` env var is a third knob for a decision nobody will ever set independently — if you
are reading console output or you asked for DEBUG, you want file and line. Deriving it means one
fewer thing in `.env.example` that can be misconfigured.

⚠️ **The coupling this creates:** `LOG_LEVEL=DEBUG` in production now silently costs 41% more per
line than `INFO`. That is the correct trade (you asked for detail) but it is *not obvious from the
env var*, which is why `configure_logging` reports `callsite_info` in its startup line (§12).
Verified by `test_callsite_info_is_omitted_in_json_but_present_at_debug`.

---

## 10. `_service_fields` — lines 112–128

```python
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
```

🍕 **Plain terms:** the **masthead and edition number** printed on every page. One page torn out of
the paper and faxed somewhere still says which paper it came from and which edition.

🔧 **Technical:** a closure-based processor factory. `fields` is built **once** at configure time;
the returned function does one dict merge per event.

❓ **What if we don't write it:** three services shipping to the same aggregator produce
indistinguishable lines. During an incident the first question is "is this the API or the worker, and
is it the version we just deployed?" — and you cannot answer it. The rollback decision depends on
`version`.

❓ **Why a factory and not a plain processor reading `get_settings()`:** a plain processor would call
`get_settings()` (an `lru_cache` lookup plus attribute access) **per log line**. The closure reads
config once. At 14,188 lines/sec that is a measurable difference for zero benefit.

❓ **Why `{**fields, **event_dict}` and not `event_dict.update(fields)`:** two reasons. Ordering —
dict insertion order is JSON key order, so `service`/`version`/`env` lead the line where a human
scanning `docker logs` wants them. And precedence — `event_dict` wins, so a call site that
deliberately passes `env="sandbox"` is not silently overwritten by the process's own value.

⚠️ **The cost, stated honestly:** it allocates a new dict per event instead of mutating. structlog's
own processors mutate for speed. Measured at **0.37 µs** for the comparable `merge_contextvars`, this
is noise next to the sanitizer's 11.65 µs — so the immutability is free *here*. It would not be free
in a processor that ran on a hot inner loop.

---

## 11. `_shared_processors` — lines 131–152

```python
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
```

🍕 **Plain terms:** the **stations on the assembly line**, in order. Each one adds a stamp to the
page. Order matters because the last station is the censor, and a censor that runs in the middle
misses everything added after it.

🔧 **Technical:** the list is used **twice** — once in `structlog.configure(processors=...)` and once
as `ProcessorFormatter(foreign_pre_chain=...)`. One list, both pipelines: that is the mechanism
behind "one shape."

| Processor | What it adds | Why it must be here |
|---|---|---|
| `merge_contextvars` | `request_id`, later `user_id`/`session_id` | the correlation story; see §21 |
| `_service_fields(config)` | `service`, `version`, `env` | §10 |
| `add_logger_name` | `logger` | **the gap this rewrite closed** — the previous version had no way to tell which module logged |
| `add_log_level` | `level` | reads `_record.levelname` for foreign records |
| `PositionalArgumentsFormatter()` | resolves `"took %d ms", 12` | foreign libraries log this way; without it the args vanish |
| `TimeStamper(fmt="iso", utc=True)` | `timestamp` | `utc=True` → trailing `Z` |
| `StackInfoRenderer()` | `stack` when `stack_info=True` | opt-in per call |
| `UnicodeDecoder()` | bytes → str | LLM/tool output is sometimes bytes |
| `CallsiteParameterAdder` *(conditional)* | `filename`, `func_name`, `lineno` | §9 |
| `sanitise_event_dict` | redacts + caps | **must be last** |

❓ **Why `utc=True` and not local time:** the article's version used `datetime.now()` — naive local
time with no offset. Two containers in different regions then produce timestamps you cannot order.
Asserted by `test_json_line_carries_service_identity_and_standard_fields`, which checks the
timestamp ends with `Z`.

❓ **Why `merge_contextvars` and not the article's hand-rolled `ContextVar`:** the article defined its
own `_request_context: ContextVar[Dict]` plus `bind_context`/`clear_context`/`get_context`. That
re-implements what structlog ships, and it does not interoperate — `structlog.contextvars.bind_
contextvars()` writes somewhere the hand-rolled processor never reads. This project's
[`middleware.py`](../app/core/middleware.py) uses structlog's API, so the built-in processor is the
one that works.

🚨 **`sanitise_event_dict` last is load-bearing, not tidy.** Verified: a `request_id` bound by
middleware reaches a **foreign** stdlib line —

```
{'service': 'verify', 'env': 'test', 'event': 'i am not structlog',
 'request_id': 'req-123', 'logger': 'some.dependency', 'level': 'warning', ...}
```

— which means fields arrive from paths this file never sees. `ExtraAdder` (line 190) promotes a
dependency's `extra={...}` into real fields. If the sanitizer ran anywhere but last, a third-party
library could put a token into the output through a door your deny-list never guarded.

> **The transferable idea:** a security check belongs at the **narrowest point every path must
> cross**, not at each entrance. One processor at the end of one shared chain beats a redaction call
> at every log site, because the call site you forget is the one that leaks.

---

## 12. `configure_logging` — lines 155–216

The function everything above exists to serve. Taken in five parts.

### 12a. The structlog chain (lines 160–183)

```python
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
```

❓ **Why `filter_by_level` first — measured:**

```
suppressed INFO line:      7.13 us
emitted   WARNING line:   82.72 us      -> 11.6x cheaper
```

A `logger.debug(...)` left in an agent's inner loop costs 7 µs instead of 83 µs when the level is
`INFO`. Asserted by `test_level_filtering_drops_lines_below_configured_level`; the short-circuit
itself was verified with a spy processor that never saw the suppressed event.

🔧 **Why it works for `logger.exception()` too:** `filter_by_level` maps the *method name* to a level
via `structlog.processors.NAME_TO_LEVEL`, and `'exception'` is in it (mapping to `40`, i.e. `ERROR`).
Full key set: `critical, debug, error, exception, info, notset, warn, warning`.

❓ **Why `wrap_for_formatter` last:** it packages the finished event dict and hands it to stdlib
`logging`, where `ProcessorFormatter` unpacks it. That handoff is what lets one renderer serve both
pipelines.

### 12b. The caching decision (lines 171–182)

```python
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
```

🚨 **Beliefs #1 and #2 both lived here.** This was the "open point" the rewrite was asked to decide,
and the first two answers were both wrong.

**Wrong answer 1: "caching breaks `capture_logs()`."** It doesn't, since structlog 25.5. From
`.venv/Lib/site-packages/structlog/testing.py`:

```python
    # Modify `_Configuration.default_processors` set via `configure` but always
    # keep the list instance intact to not break references held by bound
    # loggers.
    configured_processors = get_config()["processors"]
```

`capture_logs` clears and refills **the same list object**, which cached loggers hold a reference to.
Verified both ways: with caching on, `capture_logs` captured normally, and a logger first used
*inside* a capture block resumed writing to the real sink after the block closed.

**Right answer: reconfiguration.** `configure_logging` passes a **new** list every call. Verified
probe — configure with `PROJECT_NAME="first"`, log once, reconfigure to `"second"`, log again:

| `cache_logger_on_first_use` | `service` field after reconfigure |
|---|---|
| `True` | `'first'` ← **stale config silently retained** |
| `False` | `'second'` ✅ |

[`tests/test_logging.py`](../tests/test_logging.py) reconfigures per test (`FakeConfig` variants plus
the `_restore_real_logging` fixture). With caching on, every test after the first would assert
against the first test's configuration.

❓ **What caching would actually buy:** a dict lookup, on a line that costs ~74 µs. Not measurable.

⚠️ **The trigger for revisiting:** if `configure_logging` ever becomes genuinely
call-once-per-process (no per-test reconfiguration — e.g. tests move to asserting rendered stdout
with a session-scoped configuration), then caching becomes free and should be turned on. **The
blocker is the test strategy, not production.** Write that down, because the code alone makes it look
like a performance decision.

### 12c. The foreign chain (lines 185–192)

```python
    formatter = structlog.stdlib.ProcessorFormatter(
        # `filter_by_level` is absent here on purpose: a foreign record has already passed stdlib's
        # level check, and this chain runs with `logger=None`, so the processor would raise.
        # `ExtraAdder` is first, so `logger.info(msg, extra={...})` from a dependency becomes real
        # fields -- and then gets sanitised by the tail of `shared` like everything else.
        foreign_pre_chain=[structlog.stdlib.ExtraAdder(), *shared],
        processors=[structlog.stdlib.ProcessorFormatter.remove_processors_meta, *tail],
    )
```

🚨 **The two chains differ by exactly two entries, and both differences are load-bearing.** Getting
this wrong is the single easiest way to break this file, because the obvious refactor is "pass
`shared` to both."

**Why `filter_by_level` must be absent — verified:**

```
structlog.stdlib.filter_by_level(None, "info", {"event": "x"})
-> AttributeError: 'NoneType' object has no attribute 'disabled'
```

`foreign_pre_chain` runs with `logger=None`. Put `filter_by_level` in `shared` *before* the split and
every uvicorn line raises inside the formatter.

**Why `ExtraAdder` is only in the foreign chain — verified:**

```
ExtraAdder()(logging.getLogger("x"), "info", {"event": "e"})  ->  {'event': 'e'}
```

A no-op without a `_record`. Harmless in the structlog chain, but it would be a line of code that
does nothing, in a list where every other line does something. Asserted end-to-end by
`test_foreign_stdlib_logger_is_rendered_through_the_same_pipeline`, which checks
`extra={"attempt": 2}` becomes a real `attempt` field.

⚠️ **Known incompatibility worth writing down:** `ProcessorFormatter` is **not compatible with
`logging.handlers.QueueHandler`**, the standard trick for non-blocking logging. Verified:

```
File ".../structlog/stdlib.py", line 1160, in format
    ed = cast(dict[str, Any], record.msg).copy()
AttributeError: 'str' object has no attribute 'copy'
```

`QueueHandler.prepare()` replaces `record.msg` with a formatted **string** before enqueueing, and
`ProcessorFormatter` needs the event **dict**. So "make logging async by putting a queue in front of
it" is not available here without a custom handler that preserves `msg`. Not a problem today (a
`StreamHandler` to stdout is fast and the pipe is buffered), but it is the thing you'd reach for at
14,188 lines/sec, and it does not work.

### 12d. Handler and root (lines 194–203)

```python
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    for existing in root_logger.handlers:
        # Reconfiguration (tests, `uvicorn --reload`) must not leave orphaned handlers behind.
        # `StreamHandler.close()` detaches the handler without closing sys.stdout.
        existing.close()
    root_logger.handlers = [handler]
    root_logger.setLevel(config.LOG_LEVEL)
```

❓ **Is closing the old handler safe?** Verified — `StreamHandler.close()` does not close the
underlying stream (`stream.closed == False` afterwards, still writable). It only detaches the handler
from logging's internal `_handlerList`. Without the loop, every re-configure leaks a handler.

❓ **Why `root_logger.handlers = [handler]` and not `addHandler`:** `addHandler` accumulates. Two
`configure_logging()` calls would print every line twice — the classic duplicate-log bug.

❓ **Why not `logging.basicConfig(...)`:** it is a **no-op if root already has handlers**, which is
exactly the situation after uvicorn boots. The article's version used `basicConfig` and therefore did
nothing at all under uvicorn.

⚠️ **This function is idempotent but not thread-safe.** Rebinding `root_logger.handlers` while
another thread logs is a race. Correct at startup, wrong if ever called from a request handler. It
never is — `create_app()` calls it once.

### 12e. Warnings and the startup receipt (lines 205–216)

```python
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
```

🔧 **`captureWarnings(True)`** redirects the `warnings` module into the `py.warnings` logger.
Verified: a `warnings.warn("deprecated thing")` produced a JSON line with `logger: "py.warnings"`.

🎯 **Agentic AI angle:** the LangChain/LangGraph stack deprecates aggressively across minor versions.
Those warnings are your early signal that an upgrade is about to break an agent — and by default
they go to stderr, unstructured, un-aggregated, and invisible in production.

❓ **Why log a startup receipt at all:** it answers the 3am question "did this pod actually pick up
`LOG_LEVEL=WARNING`, or is it still on the default?" without shelling into the container. It reports
`callsite_info` because that is *derived* (§9) and therefore not visible in any env var. Real output:

```json
{"service": "bench", "version": "0", "env": "test", "log_level": "INFO",
 "log_format": "json", "callsite_info": false, "event": "logging_configured",
 "logger": "app.core.logging", "level": "info", "timestamp": "2026-08-18T17:01:37.976774Z"}
```

⚠️ **The cost:** every test that captures stdout sees this line. `tests/test_logging.py` filters it
out in its `emitted_lines()` helper — a small permanent tax on the test suite, accepted for the
operational payoff.

---

## 13. `_take_over_managed_loggers` — lines 219–233

```python
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
```

🍕 **Plain terms:** walking down to the basement, unplugging each department's private press, and
telling them to file upstairs from now on.

❓ **Why `setLevel(NOTSET)` rather than leaving the level alone.** This is the subtle one. Python
checks the level on the **originating** logger, then walks ancestors for *handlers*. uvicorn pins
`uvicorn.error` to `INFO` (`level=20`, verified above). Set root to `WARNING` and uvicorn's INFO
lines **still emit**, because `uvicorn.error` says INFO is fine and root's handler doesn't re-check.
`NOTSET` makes it inherit, so `LOG_LEVEL` actually governs. Asserted by
`test_managed_dependency_loggers_are_taken_over`, which checks `uvicorn.error.level == NOTSET` and
`uvicorn.access.level == WARNING`.

❓ **Why `handlers = []` and not `removeHandler` in a loop:** mutating a list while iterating it skips
entries. Rebinding is one line and cannot half-succeed.

⚠️ **Ordering constraint, undocumented in the code:** this must run **after** `root_logger` is set up
(it is — line 205, after 202). It is order-dependent on nothing else, but a refactor that hoists it
above the root handler assignment would leave a window with no handler anywhere.

---

## 14. `get_logger` — lines 236–238

```python
def get_logger(name: str) -> structlog.stdlib.BoundLogger:
    """Return a structlog logger bound to `name` -- the one call sites use (DIP)."""
    return structlog.get_logger(name)
```

🔧 **Technical:** a one-line pass-through that returns a `BoundLoggerLazyProxy`, resolved to a real
`BoundLogger` on first use.

❓ **Why wrap `structlog.get_logger` at all — isn't this pointless indirection?** It is the one
abstraction in these files that earns its keep for a reason that is *not* substitutability: it is the
**single grep target**. Every module does `from app.core.logging import get_logger`, so swapping the
logging library, adding a default bind, or enforcing a naming convention is one edit. If 40 modules
called `structlog.get_logger` directly, it would be 40.

⚠️ **What it does not do:** the `name` argument is not validated or namespaced. Every call site
passes `__name__` by convention, and nothing enforces it. A module passing `"mylogger"` produces a
`logger` field that doesn't match the module path, and you'd only notice when filtering by it.

---

## 15. Sanitizer docstring — lines 1–12

```python
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
```

The "walking it twice" claim in this docstring is the one that verification **supported**: at 11.65 µs
flat and 38.10 µs nested, the traversal is the most expensive step in the chain (§19), so a second
one would be the worst available change.

---

## 16. The deny-lists and the caps — lines 22–85

```python
REDACTED = "***"
```

❓ **Why a constant and not the literal `"***"`:** tests assert against it
(`test_credentials_are_redacted_end_to_end` imports `REDACTED`), so the marker can change without
editing assertions. It is also the string you grep for in production to find out *whether* redaction
is firing.

### The exact-key set (lines 27–56)

```python
_SENSITIVE_KEYS = frozenset(
    {
        "accesskey",
        "accesstoken",
        "apikey",
        ...
        "token",
    }
)
```

🔧 **Technical:** compared against a **normalised** key — lowercased with all non-alphanumerics
stripped by `_KEY_NOISE` (line 74). So `API-Key`, `api_key`, `apiKey` and `APIKEY` all collapse to
`apikey` and need **one** entry.

❓ **Why normalise instead of listing variants:** the variants are unbounded. HTTP headers use
`X-Api-Key`, Python uses `api_key`, JavaScript payloads use `apiKey`, and an LLM tool call can
produce any of them. Verified across `password`, `API-Key`, `openai_api_key`, `jwt`, `token`,
`set_cookie`, `client_secret`, `user_credentials` by
`test_sensitive_key_variants_are_redacted`.

### The fragment list, and the trap it avoids (lines 64–72)

```python
# `token` is deliberately NOT a fragment: `prompt_tokens` / `completion_tokens` / `total_tokens`
# are the cost and throughput metrics of an agentic system, and redacting them would blind the
# thing this pipeline exists to observe. Bare `token` is caught by _SENSITIVE_KEYS instead.
_SENSITIVE_FRAGMENTS = (
    "apikey",
    "authorization",
    "credential",
    "passphrase",
    "password",
    "privatekey",
    "secret",
)
```

🚨 **This is the single most important line in the file, and it is a comment.** The obvious deny-list
includes `token` as a substring — it catches `access_token`, `auth_token`, `bearer_token`. It also
catches `prompt_tokens`, `completion_tokens` and `total_tokens`, because normalising
`prompt_tokens` gives `prompttokens`, which contains `token`.

🎯 **Agentic AI angle:** in an ordinary web service, losing a field called `total_tokens` costs you
nothing. In an agentic system those three fields **are** your cost model and your context-window
budget. A deny-list written by reflex would have silently replaced your entire spend telemetry with
`***`, and the failure is invisible — the logs still arrive, still parse, still have the field. You
would discover it when finance asked why token spend was unattributable.

Verified both directions: `test_sensitive_key_variants_are_redacted` (8 credential shapes redacted)
and `test_correlation_ids_and_token_metrics_survive` (`prompt_tokens`, `total_tokens`,
`token_budget`, `session_id`, `request_id` all pass through untouched).

❓ **Why is `session_id` not redacted?** It is a **correlation** id, not a credential. Redacting it
would destroy the ability to trace one user's conversation across requests — which is most of what
you want logs for in a multi-turn agent. A session *key* (`sessionkey`) is in the deny-list; a
session *id* is not. That distinction is deliberate and worth re-deriving before anyone "tightens"
it.

### The caps (lines 76–85)

```python
# An LLM prompt or completion is unbounded; a log line is not. Aggregators drop or clip oversized
# lines, which loses the *whole* event including the fields you actually needed -- so cap the
# offending value here, where the cap is visible and greppable, rather than at the collector.
_MAX_VALUE_CHARS = 2_000
_MAX_COLLECTION_ITEMS = 50
_MAX_DEPTH = 6

# Live objects consumed further down the chain, not data: `exc_info` is a traceback tuple and
# `stack_info` is already-rendered text. Walking them is wrong as well as expensive.
_PASSTHROUGH_KEYS = frozenset({"exc_info", "stack_info"})
```

🎯 **Agentic AI angle — the reason these three numbers exist at all.** An ordinary web app logs
scalars: a user id, a status code, a duration. An agent logs *payloads*: the prompt, the completion,
the retrieved chunks, the tool result. All four are unbounded, and all four are things you legitimately
want in a log line. Without caps, one 200 KB completion becomes one 200 KB log line, and most
aggregators respond by **dropping the whole event** — so the field you actually needed disappears
because of a field you didn't.

| Cap | Value | What it bounds | Verified by |
|---|---|---|---|
| `_MAX_VALUE_CHARS` | 2000 | a prompt/completion string | `test_oversized_string_is_capped_with_the_original_length` — a 5000-char value renders at **2032 chars** ending `[truncated, 5000 chars total]` |
| `_MAX_COLLECTION_ITEMS` | 50 | retrieved chunks, message history | `test_oversized_collection_is_capped` — 500 items → 51 entries, last one `...[truncated, 500 items total]` |
| `_MAX_DEPTH` | 6 | nested LangChain state | `test_deeply_nested_payload_is_elided_rather_than_walked_forever` — 20 levels deep, `bottom` never appears |

❓ **Why keep the original length in the marker:** `[truncated, 5000 chars total]` tells you the value
*was* 5000 chars. Truncating silently means you cannot tell a 2001-char value from a 2-MB one, and
"the prompt got enormous" is exactly the incident you'd be investigating.

❓ **Why `_PASSTHROUGH_KEYS`:** `exc_info` is a live `(type, value, traceback)` tuple. Recursing into a
traceback object would walk frame objects and their locals — expensive, and it could *serialise
secrets out of local variables* that `dict_tracebacks` deliberately excludes (`show_locals=False`).
The passthrough is a security decision disguised as a performance one.

---

## 17. The traversal — lines 88–137

```python
def _is_sensitive(key: str) -> bool:
    """True when a key's *value* is a credential and must be replaced rather than logged."""
    normalised = _KEY_NOISE.sub("", key.lower())
    return normalised in _SENSITIVE_KEYS or any(fragment in normalised for fragment in _SENSITIVE_FRAGMENTS)
```

🔧 **Technical:** exact-set membership (O(1)) *then* fragment scan (7 substring checks). Order
matters for cost, not correctness — the common case is a non-sensitive key, which pays for both.

```python
def _sanitise_value(value: Any, depth: int) -> Any:
    """Apply leaf policy to one value, recursing into containers up to `_MAX_DEPTH`."""
    if isinstance(value, SecretStr):
        # Redacted by type, not by key name: a SecretStr is never loggable regardless of the key it
        # was bound under. `repr()` would already mask it, but this keeps one marker in the output.
        return REDACTED
```

🚨 **The `SecretStr` branch is belt-and-braces, and the comment says so honestly.** Verified — a raw
`SecretStr` through `JSONRenderer` with no sanitizer at all renders as:

```json
{"event": "e", "k": "SecretStr('**********')"}
```

pydantic's `__repr__` already masks it. So this branch prevents **zero** leaks today. It stays
because (a) it produces one consistent `***` marker instead of a second format you'd have to grep
for separately, and (b) it is defence against a future renderer configured with a different
`default=` serialiser that calls `str()` on unknown types. Asserted by
`test_secretstr_is_redacted_regardless_of_key_name`.

```python
    if isinstance(value, Mapping):
        if depth >= _MAX_DEPTH:
            return f"[nested mapping elided at depth {_MAX_DEPTH}]"
        return _sanitise_mapping(value, depth + 1)
```

❓ **Why is the depth check inside the container branches and not at the top of the function:** a
depth cap must bound **recursion**, not values. Checking at the top would replace a perfectly good
scalar at depth 6 with an elision marker for no reason. Only containers can recurse, so only
containers are gated.

❓ **Why `isinstance(value, Mapping)` and not `dict`:** LangChain and pydantic pass dict-*like*
objects. A `dict`-only check would let a `Mapping` subclass through the traversal entirely —
unredacted — because it would fall to the final `return value`. This is the kind of hole that only
shows up with the specific library that triggers it.

```python
def _sanitise_collection(collection: Any, depth: int) -> list[Any]:
    """Rebuild a collection, keeping at most `_MAX_COLLECTION_ITEMS` entries."""
    items = list(collection)
    kept: list[Any] = [_sanitise_value(item, depth) for item in items[:_MAX_COLLECTION_ITEMS]]
    if len(items) > _MAX_COLLECTION_ITEMS:
        kept.append(f"...[truncated, {len(items)} items total]")
    return kept
```

⚠️ **`list(collection)` materialises the whole thing before slicing.** For a 500-item list that is
fine. For a generator it would **consume it**, and for a 10-million-element sequence it would copy
all of it just to keep 50. The lazy version (`itertools.islice`) was not written because nothing in
this codebase logs a generator yet. **The trigger:** the first time a log line passes a lazily
evaluated sequence, this becomes a bug rather than a cost.

⚠️ Sets and tuples come out as JSON **lists** — irreversible but unavoidable, since JSON has no set
or tuple type.

---

## 18. `sanitise` + `sanitise_event_dict` — lines 140–166

```python
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
```

> 🚨 **Updated 2026-08-19 — this was one function, and that was a security hole.** The policy was
> only reachable as a structlog processor, so it guarded log lines and nothing else. When
> `exception_handlers.py` gained a DEBUG-mode response body carrying exception context, that body
> rendered `api_key` **verbatim** while the log line redacted it — and an HTTP response is the *more*
> exposed sink, since people paste responses into tickets. `sanitise()` is now the policy and
> `sanitise_event_dict` a three-line adapter. See
> [`5_exception_handling_guide.md`](./5_exception_handling_guide.md) §21 and
> `test_debug_response_body_is_redacted`.

🔧 **Technical:** the structlog processor signature is `(logger, method_name, event_dict)`. The first
two are unused in the adapter, hence the leading underscores.

❓ **Why `key.startswith("_")`:** structlog's `ProcessorFormatter` passes `_record` (a live
`LogRecord`) and `_from_structlog` (a bool) through the chain and strips them later via
`remove_processors_meta`. Recursing into a `LogRecord` would walk its `__dict__` including `args` and
`exc_info`. The underscore convention is structlog's own marker for "internal, hands off."

❓ **Why return a new dict instead of mutating:** because `logger.info("x", payload=my_dict)` passes
**your** object. Mutating it would mean the act of logging a config dict silently replaces its
`password` field with `***` in the running application — a debugging nightmare where the bug appears
only when logging is enabled. Asserted by `test_sanitiser_does_not_mutate_the_callers_dict`.

✅ **The end-to-end proof.** Verified that a real secret cannot reach stdout:

```json
{"service": "bench", "version": "0", "env": "test", "api_key": "***",
 "nested": {"headers": {"Authorization": "***"}}, "secret_obj": "***",
 "prompt_tokens": 812, "event": "llm_call", "logger": "bench"}
```

Three different leak paths (top-level key, nested-mapping key, `SecretStr` under an innocent name)
all closed, and `prompt_tokens` survives.

---

## 19. Measured performance

Every number here came from `timeit` on this machine (Python 3.12.7, structlog 26.1.0, Windows).
They are **relative** guides, not SLOs.

### One log line, production settings

```
70.48 us/line   ->  14,188 lines/sec on one core
```

### Where that time goes

| Processor | flat event | nested agent payload |
|---|---|---|
| `sanitise_event_dict` | 11.65 µs | 38.10 µs |
| `JSONRenderer` | 4.71 µs | — |
| `CallsiteParameterAdder` | 4.61 µs | 4.84 µs |
| `TimeStamper(iso, utc)` | 2.79 µs | — |
| `UnicodeDecoder` | 0.76 µs | — |
| `StackInfoRenderer` | 0.41 µs | — |
| `merge_contextvars` | 0.37 µs | — |
| `add_log_level` | 0.23 µs | — |

### The three decisions these numbers justify

| Decision | Evidence |
|---|---|
| `filter_by_level` first | suppressed line **7.13 µs** vs emitted **82.72 µs** → **11.6× cheaper** |
| callsite gated to console/DEBUG | **73.62 µs** → **103.55 µs** with it on → **+41%** |
| no logger caching | upside is one dict lookup on a 74 µs line; cost is stale config on reconfigure |

### The price of the security guarantee

| Payload | line total | sanitizer share |
|---|---|---|
| flat (7 scalar fields) | 76.05 µs | 9.45 µs — **12.4%** |
| nested (8 messages × 400 chars) | 117.55 µs | 33.75 µs — **28.7%** |

⚠️ **Write this down as accepted debt.** Nearly a third of the cost of logging a realistic agent
payload is the sanitizer. That is the correct trade — the alternative is leaking credentials — but if
logging ever shows up in a profile, **this** is the line item, and the fix is to log smaller payloads
rather than to weaken the traversal.

---

## 20. SOLID scorecard

| Principle | How these files honour it |
|---|---|
| **S** — Single Responsibility | Four actors, four homes: pipeline shape (`logging.py`), leaf-value policy (`log_sanitizer.py`), per-request context (`middleware.py`), error→response mapping (`exception_handlers.py`). The article's single file did logging config, context management, file I/O, JSON serialisation and startup logging. |
| **O** — Open/Closed | New format = one row in `_TAIL_PROCESSORS`. New universal field = one entry in `_shared_processors`. New chatty dependency = one row in `_MANAGED_LOGGERS`. New credential shape = one string in `_SENSITIVE_KEYS`. **`configure_logging()` itself changes for none of them.** |
| **L** — Liskov Substitution | Anything with the five `LoggingConfig` attributes works: real `Settings`, the `FakeConfig` dataclass in tests, a future `RemoteSettings`. `configure_logging` cannot tell them apart. |
| **I** — Interface Segregation | `logging.py` depends on a 5-field Protocol, not 20-field `Settings`. `log_sanitizer.py` depends on **nothing from this project** — only `re`, `Mapping`, and `SecretStr`. |
| **D** — Dependency Inversion | Call sites depend on `get_logger` (a function) rather than on `structlog`. `logging.py` depends on `sanitise_event_dict` as a *processor-shaped callable*, not on a `Sanitizer` class. |

### ⚠️ Where SOLID is deliberately NOT applied

**There is no `LogRenderer` interface with `JsonRenderer`/`ConsoleRenderer` implementations.** structlog
already defines the processor contract — a callable `(logger, method_name, event_dict)`. Wrapping that
in a project-local ABC would add a hierarchy that converts *nothing*: `_TAIL_PROCESSORS` is already a
registry of substitutable implementations, and a dict of callables is the lighter form of the same
polymorphism.

**There is no `Sanitizer` class with an injectable policy object.** `_SENSITIVE_KEYS` is a
module-level `frozenset`, not a constructor argument. A class would let you configure the deny-list
per environment — which is precisely the flexibility you **don't** want: "redact less in staging" is
how secrets end up in a staging log that someone pastes into a ticket. The deny-list being a
non-negotiable module constant *is* the security property.

**`_service_fields` is a closure, not a class with `__call__`.** Identical behaviour, one third the
code, and it cannot accumulate state between events.

> **The transferable idea:** before adding an interface, ask **what will be substituted at runtime,
> by whom.** `_TAIL_PROCESSORS` has two real implementations chosen by an env var — that is a
> registry. A `Sanitizer` ABC would have exactly one implementation forever, and its only real effect
> would be making the deny-list overridable, which is a security regression dressed as flexibility.

---

## 21. Where this fits in the 7 layers

```
   YOUR CODE                    DEPENDENCIES (uvicorn, httpx, LangChain)
   get_logger(__name__)         logging.getLogger("httpx")
         │                                  │
         │ structlog chain                  │ stdlib record
         ▼                                  ▼
  ┌──────────────────┐            ┌──────────────────────┐
  │ filter_by_level  │            │  ExtraAdder()        │  ← extra={} becomes fields
  │  (11.6x saving)  │            └──────────┬───────────┘
  └────────┬─────────┘                       │
           └──────────────┬──────────────────┘
                          ▼
        ┌─────────────────────────────────────────────┐
        │           _shared_processors()              │
        │  merge_contextvars   ← request_id (L6)      │
        │  _service_fields     ← service/version/env  │
        │  add_logger_name, add_log_level             │
        │  TimeStamper(utc)  StackInfo  Unicode       │
        │  [CallsiteParameterAdder]  ← console/DEBUG  │
        │  ─────────────────────────────────────────  │
        │  sanitise_event_dict   ← THE CENSOR, LAST   │
        └───────────────────┬─────────────────────────┘
                            ▼
                 ┌──────────────────────┐
                 │  _TAIL_PROCESSORS    │  json → dict_tracebacks + JSONRenderer
                 │  [LOG_FORMAT]        │  console → ConsoleRenderer
                 └──────────┬───────────┘
                            ▼
                 StreamHandler(sys.stdout)
                            │
              ┌─────────────┴─────────────┐
              ▼                           ▼
      Docker/k8s log driver        (later) Langfuse traces — L6
```

**Why this is Layer 0 infrastructure serving Layer 6 (Observability):** every layer logs, so the
pipeline cannot live inside any one of them. It sits next to [`config.py`](../app/core/config.py) and
[`exceptions.py`](../app/core/exceptions.py) — the modules with almost no dependencies of their own.

| Ordinary web service | Agentic AI system |
|---|---|
| One request → one or two log lines | One request → 16+ lines (12 tool calls, 4 LLM round-trips), most from **dependencies** |
| Log values are scalars (id, status, ms) | Log values are **payloads** (prompt, completion, retrieved chunks) — unbounded by nature |
| A leaked field is a config value | A leaked field is a **prompt containing client PII**, or a key with a per-token cost attached |
| `total_tokens` is meaningless | `total_tokens` **is the cost model** — redacting it by accident destroys spend attribution (§16) |
| Failure is an exception you catch | Failure is an agent that *degrades* — logs are the only signal, so they are the audit trail |
| Access log ≈ the request record | Middleware's `request_finished` is a strict superset; the access log is pure duplication (§6) |

---

## 22. How to extend it

### Add a field to every log line (e.g. OpenTelemetry `trace_id`)

```python
# in _shared_processors(), before sanitise_event_dict
processors.append(add_otel_trace_context)   # one entry
```
Nothing else changes — both pipelines share the list.

### Add `user_id` / `session_id` for the auth layer

No change here at all. Bind them in middleware and `merge_contextvars` carries them:

```python
structlog.contextvars.bind_contextvars(user_id=claims["sub"], session_id=session.id)
```
Verified that contextvars reach even foreign dependency lines (§11), so an httpx line inside a
tool call is attributable to the user who triggered it.

### Add a new output format (`logfmt`)

```python
_TAIL_PROCESSORS["logfmt"] = (
    structlog.processors.format_exc_info,
    structlog.processors.LogfmtRenderer(),
)
```
One row. `_tail_processors_for` picks it up and the error message's `valid_formats` updates itself.

### Redact a new credential shape

```python
# log_sanitizer.py, _SENSITIVE_KEYS
"xapitoken",     # normalised form of X-Api-Token / x_api_token / xApiToken
```
Add the **normalised** spelling (lowercase, no separators). Then add a case to
`test_sensitive_key_variants_are_redacted`.

### Tame a newly chatty dependency

```python
# _MANAGED_LOGGERS
"langchain_core": logging.WARNING,
```

### What is deliberately NOT built, and why deferring was right

| Not built | Why | Trigger to build it |
|---|---|---|
| Log sampling / rate limiting | No LLM code exists yet, so there is no measured hot log path to sample | a single `event` value dominating volume |
| Async logging via `QueueHandler` | **Does not work** with `ProcessorFormatter` (§12c) — needs a custom handler | stdout writes appearing in a latency profile |
| OpenTelemetry `trace_id`/`span_id` | Nothing produces spans yet; the processor slot is a one-liner when it does | first distributed trace across services |
| GenAI semantic-convention fields (`gen_ai.*`) | No LLM call site to emit them | Langfuse/OTel wiring in Layer 6 |
| Log-level override per module | One global `LOG_LEVEL` plus `_MANAGED_LOGGERS` has covered every case so far | needing DEBUG for one module in production |
| PII detection (names, emails) beyond key-name matching | Key-name matching is deterministic and fast; content matching needs a classifier and produces false positives | a compliance requirement naming content, not fields |

---

## 23. Cheat sheet

```
USE IT
  every module     from app.core.logging import get_logger
                   logger = get_logger(__name__)
  log an event     logger.info("event_name_in_snake_case", key=value, ...)
  log an error     logger.exception("what_failed")        ← inside `except`, adds traceback
  add context      structlog.contextvars.bind_contextvars(user_id=..., session_id=...)
  configure        configure_logging(get_settings())      ← once, in create_app()

THE TWO CHAINS (differ by exactly two entries — do not unify them)
  structlog      [filter_by_level] + shared + [wrap_for_formatter]
  foreign        [ExtraAdder]      + shared
  why            filter_by_level raises on logger=None; ExtraAdder is a no-op without _record

CHAIN ORDER (sanitizer LAST, always)
  filter_by_level -> merge_contextvars -> service fields -> logger name -> level
  -> positional args -> timestamp(utc) -> stack info -> unicode
  -> [callsite if console/DEBUG] -> SANITISE -> renderer

FOUR EXTENSION POINTS (one row each, never touch configure_logging)
  new format         _TAIL_PROCESSORS["logfmt"] = (...)
  new global field   _shared_processors() append
  chatty dependency  _MANAGED_LOGGERS["pkg"] = logging.WARNING
  new secret shape   _SENSITIVE_KEYS / _SENSITIVE_FRAGMENTS   (normalised spelling)

REDACTION RULES
  normalised key     lowercase, strip non-alphanumerics    api_key/API-Key/apiKey -> apikey
  redacted           exact set hit, fragment hit, or any SecretStr value
  NOT redacted       prompt_tokens, total_tokens, token_budget, session_id, request_id
  capped             strings >2000 chars, collections >50 items, nesting >6 deep
  untouched          keys starting with "_", exc_info, stack_info

MEASURED (this machine, py3.12.7 / structlog 26.1)
  70.48 us/line, 14,188 lines/sec       production settings
  7.13 us  vs  82.72 us                 suppressed vs emitted   (11.6x — filter_by_level first)
  73.62 us -> 103.55 us                 callsite OFF -> ON      (+41%)
  sanitizer = 12.4% of a flat line, 28.7% of a nested agent payload

NEVER
  x import logging; logging.info(...)          bypasses structlog; no context, no redaction
  x logger.info(f"user {user_id} did x")       f-string kills structured search — pass key=value
  x logger.info("msg", token=api_key)          redacted, but say what you mean; never log secrets
  x logging.basicConfig(...)                   no-op once uvicorn has installed handlers
  x root.addHandler(...) in configure_logging  accumulates -> every line printed twice
  x a file handler "for durability"            the platform rotates and ships; you will not
  x cache_logger_on_first_use=True             re-configure silently ignored (§12b)
  x QueueHandler in front of ProcessorFormatter  AttributeError: 'str' has no attribute 'copy'
  x adding "token" to _SENSITIVE_FRAGMENTS     nukes prompt_tokens/total_tokens — your cost model
  x calling configure_logging from a request    rebinds root.handlers; not thread-safe
```

### Verification commands

```bash
uv run pytest tests/test_logging.py -q        # 31 tests
uv run pytest -q                              # 55 tests, app/ at 100% coverage
uv run ruff check . && uv run ruff format --check .
uv run mypy app                                # 1 pre-existing error in main.py:44 (FastAPI typing)

# see the real production shape
LOG_FORMAT=json uv run python -c "from app.main import create_app; create_app()"

# prove redaction end to end
LOG_FORMAT=json uv run python -c "
from app.core.logging import configure_logging, get_logger
from app.core.config import get_settings
configure_logging(get_settings())
get_logger('demo').info('llm_call', api_key='sk-LEAK', prompt_tokens=812)"
```

---

## 📎 Related files

| File | Relationship |
|---|---|
| [`app/core/config.py`](../app/core/config.py) | supplies the 5 fields via the `LoggingConfig` Protocol — see [`3_config_py_guide.md`](./3_config_py_guide.md) |
| [`app/core/middleware.py`](../app/core/middleware.py) | binds `request_id`/`method`/`path` that `merge_contextvars` picks up; emits `request_started`/`request_finished` |
| [`app/core/exceptions.py`](../app/core/exceptions.py) | `ConfigurationError`, raised by `_tail_processors_for` |
| [`app/core/exception_handlers.py`](../app/core/exception_handlers.py) | the one place an exception becomes a log line + a response — see [`5_exception_handling_guide.md`](./5_exception_handling_guide.md) |
| [`app/core/error_context.py`](../app/core/error_context.py) | produces the `blame`/`failed_at`/`app_traceback` fields these log lines carry |
| [`app/main.py`](../app/main.py) | calls `configure_logging(settings)` inside `create_app()` |
| [`tests/test_logging.py`](../tests/test_logging.py) | 31 tests; every claim in this guide is asserted or measured there |
| [`.env.example`](../.env.example) | `LOG_LEVEL`, `LOG_FORMAT` — see [`1_env_guide.md`](./1_env_guide.md) |

---

*Last updated: 2026-08-19 | Based on `app/core/logging.py` (238 lines) and `app/core/log_sanitizer.py` (154 lines) of the `production_agentic_ai` project*
