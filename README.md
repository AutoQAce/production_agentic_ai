# Production Agentic AI

Infrastructure for running LLM agents in production: typed configuration, structured
logging, credential redaction, request correlation, and an error path that tells you
which line of *your* code failed.

FastAPI · LangGraph · structlog · Pydantic Settings · Postgres · Prometheus · Grafana

---

## Status

The foundation and observability layers are built and tested. The agent layers are
scaffolded but empty — `app/api`, `app/services`, `app/models`, `app/schemas` and
`app/core/langgraph` currently contain only `__init__.py`.

| Built | Module |
|---|---|
| Tiered configuration with fail-fast startup policy | `app/core/config.py` |
| Structured logging pipeline | `app/core/logging.py` |
| Credential redaction and value capping | `app/core/log_sanitizer.py` |
| Exception taxonomy | `app/core/exceptions.py` |
| Stack introspection / blame frames | `app/core/error_context.py` |
| Log + HTTP response for every failure family | `app/core/exception_handlers.py` |
| Request correlation and lifecycle logging | `app/core/middleware.py` |

82 tests, 99.55% coverage on `app/`, `ruff` and `mypy` clean.

---

## Quick start

```bash
uv sync
cp .env.example .env.development
make run                      # uvicorn on :8000
curl localhost:8000/health
```

The full local stack — API, Postgres, Prometheus, Grafana — comes up with:

```bash
make docker-up
```

Requires [uv](https://docs.astral.sh/uv/). `pip` is not supported; it bypasses the lockfile.

---

## What's actually interesting here

### One log line locates the failure

`error_context.py` walks the exception chain and discards every frame that isn't yours.
A production request is 40+ frames deep — uvicorn, starlette, fastapi, **your code**,
langchain, httpx, ssl — and the deepest frame is almost never the one you need.

Real output, JSON renderer, abridged:

```json
{
  "event": "app_exception",
  "exception_type": "ValueError",
  "exception_message": "anthropic returned 503",
  "failed_at": "app/services/llm.py:42 in LLMService.invoke",
  "app_traceback": ["app/services/llm.py:42 in LLMService.invoke",
                    "app/api/v1/chat.py:18 in chat"],
  "api_key": "***",
  "request_id": "9f2c…", "level": "error", "timestamp": "…"
}
```

`failed_at` is flat and indexable, so *"every failure in `LLMService.invoke` this week"*
is a log query rather than an afternoon of grepping. The full traceback is attached
separately via `exc_info` and stays in the message body.

This is not free — naive frame walking cost 40ms per failure, and errors arrive in
bursts, exactly when the service is already degraded. A cached path classifier and a
single traceback walk brought it to 39µs. See `scripts/bench_error_context.py`.

### Credentials never reach a sink

Redaction is a policy (`sanitise()`), not a log processor, because a DEBUG response body
is a second sink for the same context — and the more exposed of the two, since developers
paste HTTP responses into tickets. Both paths run through it.

`token` is deliberately *not* a redaction rule: `prompt_tokens` / `completion_tokens` /
`total_tokens` are an agentic system's cost model and have to survive.

### Configuration refuses to boot when it's wrong

`APP_ENV` maps to a deployment tier, and the tier sets policy that cannot be overridden
by a `.env` file: no `DEBUG` outside development, no wildcard CORS in production, a
minimum `JWT_SECRET_KEY` length. A misconfigured container fails at startup with a named
error rather than serving traffic with the wrong settings.

### Every error answers in one shape

```json
{"error": "rate_limit_exceeded", "message": "…", "error_id": "…", "request_id": "…"}
```

Including 404s and 422s, which FastAPI otherwise answers with `{"detail": …}`. Clients
parse one envelope. `request_id` is bound to structlog's contextvars by the middleware,
so it appears on every log line emitted anywhere downstream without being threaded
through a single function signature — and it comes back to the caller in the
`X-Request-ID` header, which is what makes a user's screenshot traceable to a log line.

---

## Layout

```
app/
  core/          config, logging, sanitizer, exceptions, error_context,
                 exception_handlers, middleware      ← built
  api/v1/        route handlers                      ← scaffold
  services/      business logic                      ← scaffold
  models/        SQLModel tables                     ← scaffold
  schemas/       Pydantic request/response           ← scaffold
  core/langgraph agent graph + tools                 ← scaffold
evals/           LLM-as-a-judge evaluation harness   ← scaffold
scripts/         reproducible benchmarks
docs/            module-by-module guides
grafana/ prometheus/   observability stack config
```

## Docs

`docs/` explains the shipped modules line by line, including the measured numbers behind
each decision and the alternatives that were rejected.

| | |
|---|---|
| [1_env_guide](docs/1_env_guide.md) | environment files and secret handling |
| [2_pyproject_toml_guide](docs/2_pyproject_toml_guide.md) | dependency groups, ruff, mypy, pytest config |
| [3_config_py_guide](docs/3_config_py_guide.md) | settings, tiers, startup validation |
| [4_logging_guide](docs/4_logging_guide.md) | the structlog pipeline and its benchmarks |
| [5_exception_handling_guide](docs/5_exception_handling_guide.md) | the error path end to end |

## Development

```bash
make test                       # pytest, 80% coverage floor enforced
make lint                       # ruff
uv run mypy .
uv run pre-commit run --all-files
uv run python scripts/bench_error_context.py
uv run python scripts/bench_logging.py
```
