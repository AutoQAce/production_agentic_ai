# ADR-0001 — Surfacing configuration failures raised before logging exists

> Architecture Decision Record. Write this **before** building (see `LEARNING_ROADMAP.md` → Architect Track).
> After the build, fill **Actual failure modes** and refresh the row in `../MASTER_INDEX.md` → Design Decisions Log.

| Field | Value |
|---|---|
| ADR # | 0001 |
| Date | 2026-09-06 |
| Status | Accepted |
| Phase | 9 (Production Infrastructure & Scale) — Layer 0 foundation work |
| Notebook / module | `app/core/logging.py`, `app/main.py` |
| Patterns touched | startup validation, structured logging, exception taxonomy, sink coverage |

## Problem & Constraints

`create_app()` must read settings before it can configure logging, because the logging pipeline is
itself configured *from* settings (`LOG_LEVEL`, `LOG_FORMAT`). That ordering is not negotiable:

```python
settings = get_settings()      # can raise ConfigurationError
configure_logging(settings)    # the only thing that renders errors nicely starts here
```

So there is a window at process start with **no log pipeline**, and the one failure family
guaranteed to land in it is the `ConfigurationError` that reading settings raises.

`AppException` deliberately separates three audiences (`log_context()`, `client_payload()`,
`debug_payload()`). Python's default traceback uses none of them — it prints `str(exc)`, which is
only `message`. Verified against the real failure path:

```
$ APP_ENV=prd python -c "from app.core.config import get_settings; get_settings()"

reaches the operator:  ConfigurationError: Unknown APP_ENV: 'prd'
carried but discarded: hint = "add it to ENVIRONMENT_TIERS with the policy tier it belongs to"
                       known_environments = ['ci', 'dev', 'development', 'local', 'preprod', ...]
```

The operator is told they are wrong but not what right looks like, while the process is holding the
exact answer. This is the last open half of the Appendix C deviation dated 2026-07-25
(`AGENTIC_AI_PRODUCTION_BIBLE.md`), which established that logging must wrap the foundation.

- **Constraint 1:** the operator sees `hint` + context on a failed start, without a log pipeline.
- **Constraint 2:** the process still dies — reporting must never degrade into swallowing.
- **Constraint 3:** no new sink escapes redaction. `log_sanitizer.py` states the rule directly:
  *"A leak-prevention rule that only guards one sink is a rule with a hole in it."* stderr in a
  container is scraped by the same aggregator as stdout, so it is a third sink, not a free pass.
- **Constraint 4:** no duplicate or double-rendered output once logging *is* configured.

## Candidate Architectures (≥2 — never one)

- **A — Override `AppException.__str__`** to append `hint` and context, so the default traceback
  carries them everywhere, with no call-site change.
- **B — Inline `try/except` in `create_app()`**, formatting and writing to stderr in `main.py`.
- **C — `report_bootstrap_error()` in `logging.py`, called from a `try/except` in `main.py`.**
  The logging module owns emission, including the case where its own pipeline does not exist yet;
  `main.py` keeps one `try/except` and one call.
- **D — Emergency pre-config logging**: configure structlog with hardcoded defaults before reading
  settings, then reconfigure once settings load.

## Decision Matrix

Scored 1–5, higher = better.

| Criterion | A | B | C | D |
|---|---|---|---|---|
| Cost (lines / moving parts) | 5 | 4 | 4 | 1 |
| Latency | 5 | 5 | 5 | 4 |
| Reliability | 3 | 4 | 4 | 3 |
| Complexity / maintainability | 2 | 3 | 5 | 1 |
| Security (Constraint 3) | 2 | 3 | 5 | 4 |
| **Fit to the hard constraint** | 2 | 4 | 5 | 3 |

## Decision

**Chosen: C.**

**Why not A.** It looks like the smallest possible diff and is the most tempting, but it fails
Constraint 4 by corrupting a sink that is currently correct. `error_context.describe()` puts
`str(exc)` into the `exception_message` log field, and `exception_handlers._log_error()` *already*
splats `**exc.log_context()` as separate structured fields. Widening `__str__` means every logged
`AppException` carries `hint` and context twice — once flattened inside `exception_message`, once as
real fields — and the `caused_by` chain strings inherit the same bloat. Fixing an unconfigured sink
by degrading the configured one is a bad trade. It also fails Constraint 3: `__str__` has no
redaction, so a future subclass carrying a credential for debugging would print it in every
traceback, everywhere.

**Why not B.** Correct, but it puts stderr formatting and sanitiser knowledge into the app factory.
`main.py`'s value is that it is boring — read settings, configure, mount, register. Teaching it how
to render an exception is the first step toward it knowing about everything.

**Why not D.** It buys a full pipeline for a window that only ever produces one class of error, at
the cost of a hardcoded format guess, a double `configure_logging()`, and two `logging_configured`
events per boot. Over-built for the problem.

**C** puts the decision where the ownership already is. `logging.py`'s stated job is *how this
process emits a log line*; "there is no pipeline yet" is a case of that job, not a different one. It
already imports `log_sanitizer`, so Constraint 3 costs one function call rather than a new
dependency. `main.py` gains four lines and no new concepts.

## Predicted Failure Modes

- **The guard silently becomes a swallow.** Someone adds recovery logic to the `except` and drops
  the `raise`; a misconfigured process then boots → detect via `tests/test_logging.py`, which
  asserts the exception still propagates, not merely that output appeared.
- **A second entrypoint bypasses it.** A queue worker (Bible Step 14), a CLI, or Alembic's `env.py`
  calls `get_settings()` without the guard and regresses to a bare traceback → detect at review;
  the fix is to call `report_bootstrap_error()` there too, not to widen this one.
- **Non-`AppException` startup failures stay bare.** A type error (`POSTGRES_PORT=abc`) raises
  pydantic's `ValidationError`, which is not caught here. Accepted deliberately: pydantic's own
  message already names the field, the bad value and the reason, so it has no hidden context to
  surface. Revisit only if a real message proves unhelpful.
- **stderr not flushed on a hard crash** → mitigated with `flush=True`.

## Actual Failure Modes *(fill after the build, via `/adr reconcile 0001`)*

- <what actually broke / what didn't, vs. predicted>

## Consequences

**Makes easy.** Every `AppException` raised before `configure_logging()` now has a sink, and it is a
redacted one. Later entrypoints get the behaviour with a one-line call.

**Makes hard.** Nothing yet. The pre-logging window remains genuinely special — code running in it
must not assume `get_logger()` produces configured output.

**Defers.** Whether worker/CLI entrypoints share one bootstrap wrapper is left until a second
entrypoint actually exists (Bible Step 14). Building the abstraction for one caller would be
speculative; the ADR records the trigger instead.
