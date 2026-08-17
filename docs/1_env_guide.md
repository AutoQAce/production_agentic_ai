# 🔐 Environment Variables — Complete Understanding Guide

> **Purpose:** A personal reference document for the `.env.example` file.
> Covers what every variable does, why it exists, what values to use per environment,
> and how they flow into the running app. Revisit any section anytime.

---

## 📚 Table of Contents

1. [What is `.env.example`?](#what-is-envexample)
2. [How the env system works in this project](#how-the-env-system-works)
3. [Application Settings](#1-application-settings)
4. [API Settings](#2-api-settings)
5. [LLM Settings](#3-llm-settings-openai)
6. [JWT / Authentication Settings](#4-jwt--authentication-settings)
7. [Database Settings (PostgreSQL)](#5-database-settings-postgresql)
8. [Observability Settings (Langfuse)](#6-observability-settings-langfuse)
9. [Rate Limiting Settings (SlowAPI)](#7-rate-limiting-settings-slowapi)
10. [Logging Settings](#8-logging-settings)
11. [Environment Comparison Table](#9-environment-comparison-table)
12. [Quick Setup Checklist](#10-quick-setup-checklist)
13. [Security Rules — Never Break These](#11-security-rules--never-break-these)

---

## What is `.env.example`?

`.env.example` is a **template file** — it shows the shape (keys) of all environment variables your app needs, but with **fake/placeholder values** instead of real secrets.

### The golden rule:
```
.env.example   ← ✅ Safe to commit to git (no real secrets)
.env           ← ❌ NEVER commit (contains real secrets)
.env.development
.env.staging   ← ❌ NEVER commit (real secrets per environment)
.env.production
```

Think of `.env.example` like a **blank job application form** — it shows you what fields to fill in, but has no personal information written in it yet.

---

## How the Env System Works

```
.env.example
    ↓  (copy + fill in real values)
.env.development  ←  used when APP_ENV=development
.env.staging      ←  used when APP_ENV=staging
.env.production   ←  used when APP_ENV=production
    ↓
app/core/config.py   ←  pydantic-settings reads .env and maps to typed Settings class
    ↓
settings.OPENAI_API_KEY   ←  used throughout the app via `get_settings()`
```

### The `config.py` Connection

The [`Settings` class in `config.py`](../app/core/config.py) maps every `.env` variable to a typed Python attribute:

```python
class Settings(BaseSettings):
    APP_ENV: str = "development"
    OPENAI_API_KEY: str = ""
    POSTGRES_PORT: int = 5432   # automatically converts string "5432" → int
    DEBUG: bool = True           # automatically converts "true" → True
```

`pydantic-settings` reads the `.env` file automatically and validates the types.

---

## 1. Application Settings

```ini
APP_ENV=development
PROJECT_NAME="7 Layers Production Agentic AI"
VERSION=0.1.0
DEBUG=true
```

| Variable | What it does | Valid Values |
|----------|-------------|--------------|
| `APP_ENV` | Identifies which environment the app is running in | `development`, `staging`, `production` |
| `PROJECT_NAME` | Display name of the app (shown in API docs, logs) | Any string |
| `VERSION` | Current app version (shown in `/health` or `/info` endpoints) | Semver e.g. `0.1.0` |
| `DEBUG` | Enables debug mode — more verbose errors, auto-reload | `true` / `false` |

### ⚠️ Key Rules

- **`DEBUG=true` in production is a security risk.** It can expose internal stack traces to users.
- Always set `DEBUG=false` in staging and production.

### Per-Environment Values

| Variable | Development | Staging | Production |
|----------|------------|---------|------------|
| `APP_ENV` | `development` | `staging` | `production` |
| `DEBUG` | `true` | `false` | `false` |
| `VERSION` | `0.1.0` | same as dev | same as dev |

---

## 2. API Settings

```ini
API_V1_STR=/api/v1
ALLOWED_ORIGINS="http://localhost:3000,http://localhost:8000"
```

| Variable | What it does |
|----------|-------------|
| `API_V1_STR` | The URL prefix for all v1 API routes. Every endpoint lives under `/api/v1/...` |
| `ALLOWED_ORIGINS` | CORS — which frontend URLs are allowed to call this API |

### Simple Analogy for CORS

Imagine your API is a **VIP club**. `ALLOWED_ORIGINS` is the **guest list**.

- Only browsers from the listed domains can make requests to your API.
- If a browser from an unlisted domain tries → it gets blocked.

```
# Development: local frontends allowed
ALLOWED_ORIGINS="http://localhost:3000,http://localhost:8000"

# Production: only your real domain
ALLOWED_ORIGINS="https://yourdomain.com,https://www.yourdomain.com"
```

### What `API_V1_STR` does in practice

```
API_V1_STR=/api/v1

→ All routes become:
   /api/v1/auth/login
   /api/v1/chat
   /api/v1/messages
```

This allows future versioning — when you release breaking changes, you add `/api/v2/` without removing `/api/v1/`.

---

## 3. LLM Settings (OpenAI)

```ini
OPENAI_API_KEY="your-llm-api-key"
DEFAULT_LLM_MODEL=gpt-4o-mini
DEFAULT_LLM_TEMPERATURE=0.2
MAX_LLM_CALL_RETRIES=3
```

| Variable | What it does | Practical Notes |
|----------|-------------|-----------------|
| `OPENAI_API_KEY` | Your secret key to authenticate with OpenAI's API | Get from [platform.openai.com/api-keys](https://platform.openai.com/api-keys) |
| `DEFAULT_LLM_MODEL` | Which AI model to use by default | `gpt-4o-mini` (cheap, fast), `gpt-4o` (powerful) |
| `DEFAULT_LLM_TEMPERATURE` | Controls randomness in AI responses | `0.0` = deterministic, `1.0` = very creative |
| `MAX_LLM_CALL_RETRIES` | How many times to retry if the LLM API fails | Used by the `tenacity` retry decorator |

### Temperature Explained Simply

Think of `TEMPERATURE` as a **creativity dial** for the AI:

```
0.0  →  Always gives the same, most predictable answer
        Best for: code generation, structured output, factual Q&A

0.2  →  Slightly varied, but mostly consistent (this project's default)
        Best for: chat assistants, general purpose

0.7+ →  More creative and varied answers
        Best for: creative writing, brainstorming

1.0  →  Very random, sometimes surprising
        Best for: generating diverse ideas
```

### Why `MAX_LLM_CALL_RETRIES = 3`?

LLM APIs occasionally fail with network errors or rate limit hits. Instead of crashing, the app **automatically retries up to 3 times** before giving up. This is handled by the `tenacity` library in the service layer.

### Per-Environment Values

| Variable | Development | Staging | Production |
|----------|------------|---------|------------|
| `DEFAULT_LLM_MODEL` | `gpt-4o-mini` (cheap) | `gpt-4o-mini` | `gpt-4o` (powerful) |
| `DEFAULT_LLM_TEMPERATURE` | `0.2` | `0.2` | `0.2` |
| `MAX_LLM_CALL_RETRIES` | `3` | `3` | `5` |

---

## 4. JWT / Authentication Settings

```ini
JWT_SECRET_KEY="your-jwt-secret-key"
JWT_ALGORITHM=HS256
JWT_ACCESS_TOKEN_EXPIRE_DAYS=30
```

### What is JWT?

**JWT (JSON Web Token)** is like a **stamped wristband** at a concert:
- You show your ticket (password) once at the door → you get a wristband (JWT token)
- After that, you show the wristband to get into any area — no need to re-enter your password
- The wristband has an expiry — after 30 days, you need to log in again

| Variable | What it does |
|----------|-------------|
| `JWT_SECRET_KEY` | The secret stamp used to sign and verify every wristband (token). If someone gets this, they can forge tokens! |
| `JWT_ALGORITHM` | The signing method. `HS256` = HMAC with SHA-256 (standard, fast, symmetric) |
| `JWT_ACCESS_TOKEN_EXPIRE_DAYS` | How many days before a token expires and the user must log in again |

### ⚠️ Critical Security Warning

```bash
# NEVER use weak or guessable secret keys
JWT_SECRET_KEY="secret"           # ❌ Terrible
JWT_SECRET_KEY="password123"      # ❌ Terrible
JWT_SECRET_KEY="change-me"        # ❌ Default placeholder — must change!

# Generate a strong secret key
python -c "import secrets; print(secrets.token_hex(32))"
# → use the output as your JWT_SECRET_KEY
```

### Per-Environment Values

| Variable | Development | Staging | Production |
|----------|------------|---------|------------|
| `JWT_SECRET_KEY` | Any string (local only) | Strong random key | Very strong random key |
| `JWT_ACCESS_TOKEN_EXPIRE_DAYS` | `30` | `7` (shorter = safer) | `7` (shorter = safer) |

---

## 5. Database Settings (PostgreSQL)

```ini
POSTGRES_HOST=db
POSTGRES_DB=mydb
POSTGRES_USER=myuser
POSTGRES_PORT=5432
POSTGRES_PASSWORD=mypassword
```

### Simple Analogy

Think of your database like a **filing cabinet in an office**:

| Variable | Filing Cabinet Equivalent |
|----------|--------------------------|
| `POSTGRES_HOST` | Which building is the cabinet in? (`db` = Docker container name, or an IP) |
| `POSTGRES_DB` | Which drawer/room? (the database name) |
| `POSTGRES_USER` | Who are you? (your username to access it) |
| `POSTGRES_PASSWORD` | What's your password to open it? |
| `POSTGRES_PORT` | Which door number? (`5432` is PostgreSQL's default) |

### How these combine into a connection string

The `config.py` has a helper property:

```python
@property
def postgres_dsn(self) -> str:
    return (
        f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}"
        f"@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    )
```

So with the example values:
```
postgresql://myuser:mypassword@db:5432/mydb
```

This is the URL your app uses to connect to PostgreSQL.

### Why `POSTGRES_HOST=db` (not `localhost`)?

When running in **Docker Compose**, each service has a name. The PostgreSQL container is named `db` in `docker-compose.yml`. Inside the Docker network, services talk to each other by name, not `localhost`.

```
# Docker environment (docker-compose)
POSTGRES_HOST=db           # ← "db" is the docker service name

# Local machine (running postgres directly)
POSTGRES_HOST=localhost    # ← when running postgres outside docker
```

### Per-Environment Values

| Variable | Development | Staging | Production |
|----------|------------|---------|------------|
| `POSTGRES_HOST` | `db` (Docker) or `localhost` | Cloud DB host | Cloud DB host |
| `POSTGRES_DB` | `mydb` | `myapp_staging` | `myapp_prod` |
| `POSTGRES_PASSWORD` | simple for local | strong random | very strong random |

---

## 6. Observability Settings (Langfuse)

```ini
LANGFUSE_PUBLIC_KEY="your-langfuse-public-key"
LANGFUSE_SECRET_KEY="your-langfuse-secret-key"
LANGFUSE_HOST=https://cloud.langfuse.com
```

### What is Langfuse?

**Langfuse** is a **dashboard for monitoring your AI app** — like Google Analytics, but for LLM calls.

It tracks:
- Every call made to the LLM (input prompt, output, latency, cost)
- Errors and failures
- User sessions and traces
- Token usage and spend

Think of it as a **CCTV system for your AI** — you can replay and inspect every interaction.

| Variable | What it does |
|----------|-------------|
| `LANGFUSE_PUBLIC_KEY` | Safe to expose on the client side — used to identify your project |
| `LANGFUSE_SECRET_KEY` | **Never expose this** — used to authenticate from your server |
| `LANGFUSE_HOST` | Where Langfuse is hosted. Default = Langfuse's cloud. Can be self-hosted. |

### Public Key vs Secret Key

```
LANGFUSE_PUBLIC_KEY   →  Like your username — identifies you, not a secret
LANGFUSE_SECRET_KEY   →  Like your password — keep this private, server-side only
```

### Per-Environment Values

| Variable | Development | Staging | Production |
|----------|------------|---------|------------|
| `LANGFUSE_HOST` | `https://cloud.langfuse.com` | same | same (or self-hosted) |
| Keys | Dev project keys | Staging project keys | Production project keys |

> 💡 **Tip:** Create separate Langfuse projects for dev/staging/production so traces don't mix.

---

## 7. Rate Limiting Settings (SlowAPI)

```ini
RATE_LIMIT_DEFAULT="1000 per day,200 per hour"
RATE_LIMIT_CHAT="100 per minute"
RATE_LIMIT_CHAT_STREAM="100 per minute"
RATE_LIMIT_MESSAGES="200 per minute"
RATE_LIMIT_LOGIN="100 per minute"
```

### What is Rate Limiting?

**Rate limiting** is like a **bouncer at a club** — it controls how many requests a user or IP can make in a given time window. This prevents:
- Abuse and spam
- API cost overruns (LLM calls cost money!)
- Server overload from a single user

### The Format Explained

```
"100 per minute"          →  max 100 requests per 1 minute per user/IP
"1000 per day,200 per hour"  →  AND: max 1000/day AND max 200/hour
```

### What `SlowAPI` does

SlowAPI is a FastAPI-compatible rate limiting library. It reads these string values and enforces them automatically on each route:

```python
@router.post("/chat")
@limiter.limit(settings.RATE_LIMIT_CHAT)   # "100 per minute"
async def chat_endpoint(...):
    ...
```

### Per-Endpoint Breakdown

| Variable | Endpoint | Why this limit? |
|----------|----------|----------------|
| `RATE_LIMIT_DEFAULT` | All routes (fallback) | Broad protection for any unspecified route |
| `RATE_LIMIT_CHAT` | `POST /api/v1/chat` | LLM calls are expensive — limit per user |
| `RATE_LIMIT_CHAT_STREAM` | `POST /api/v1/chat/stream` | Streaming is even more resource-intensive |
| `RATE_LIMIT_MESSAGES` | `POST /api/v1/messages` | Higher — just storing messages, not LLM calls |
| `RATE_LIMIT_LOGIN` | `POST /api/v1/auth/login` | Prevent brute-force password attacks |

### Per-Environment Values

| Variable | Development | Production |
|----------|------------|------------|
| `RATE_LIMIT_DEFAULT` | `"10000 per day"` (relaxed) | `"1000 per day,200 per hour"` (strict) |
| `RATE_LIMIT_CHAT` | `"1000 per minute"` (relaxed) | `"100 per minute"` (strict) |
| `RATE_LIMIT_LOGIN` | `"1000 per minute"` | `"5 per minute"` (very strict) |

---

## 8. Logging Settings

```ini
LOG_LEVEL=DEBUG
LOG_FORMAT=console
```

| Variable | What it does | Valid Values |
|----------|-------------|--------------|
| `LOG_LEVEL` | Controls how much detail gets logged | `DEBUG`, `INFO`, `WARNING`, `ERROR`, `CRITICAL` |
| `LOG_FORMAT` | Controls how logs look | `console` (human-readable), `json` (machine-readable) |

### Log Levels — From Most to Least Verbose

```
DEBUG    →  Everything. Every step. Useful for debugging locally.
             "Fetching user 42 from database"
             "LLM response received in 1.2s"

INFO     →  Key events. Normal operation milestones.
             "Server started on port 8000"
             "User logged in: user@email.com"

WARNING  →  Something unexpected but not broken.
             "LLM retry attempt 2 of 3"
             "Rate limit reached for IP 1.2.3.4"

ERROR    →  Something failed. Needs attention.
             "Database connection failed"
             "LLM call failed after 3 retries"

CRITICAL →  App may be going down. Urgent.
             "Out of memory. Shutting down."
```

### Log Format — `console` vs `json`

**`console`** — Human-readable, good for development:
```
2026-07-25 10:30:15 | INFO | app.services.llm | LLM responded in 1.2s
```

**`json`** — Machine-readable, good for production (log aggregators like Datadog, CloudWatch):
```json
{"timestamp": "2026-07-25T10:30:15Z", "level": "INFO", "module": "app.services.llm", "message": "LLM responded in 1.2s"}
```

### Per-Environment Values

| Variable | Development | Staging | Production |
|----------|------------|---------|------------|
| `LOG_LEVEL` | `DEBUG` | `INFO` | `WARNING` |
| `LOG_FORMAT` | `console` | `json` | `json` |

> 💡 **Why `WARNING` in production?** `DEBUG` and `INFO` in production would generate **millions of log lines** daily — expensive to store and hard to search. Only log what matters.

---

## 9. Environment Comparison Table

| Variable | Development | Staging | Production |
|----------|------------|---------|------------|
| `APP_ENV` | `development` | `staging` | `production` |
| `DEBUG` | `true` | `false` | `false` |
| `DEFAULT_LLM_MODEL` | `gpt-4o-mini` | `gpt-4o-mini` | `gpt-4o` |
| `DEFAULT_LLM_TEMPERATURE` | `0.2` | `0.2` | `0.2` |
| `MAX_LLM_CALL_RETRIES` | `3` | `3` | `5` |
| `JWT_ACCESS_TOKEN_EXPIRE_DAYS` | `30` | `7` | `7` |
| `ALLOWED_ORIGINS` | `localhost:3000,8000` | staging domain | prod domain |
| `POSTGRES_HOST` | `db` (Docker) | cloud host | cloud host |
| `RATE_LIMIT_CHAT` | relaxed | moderate | `100/min` strict |
| `RATE_LIMIT_LOGIN` | relaxed | `10/min` | `5/min` |
| `LOG_LEVEL` | `DEBUG` | `INFO` | `WARNING` |
| `LOG_FORMAT` | `console` | `json` | `json` |

---

## 10. Quick Setup Checklist

When starting the project or setting up a new environment:

```
[ ] Copy .env.example to the right file:
      cp .env.example .env.development
      cp .env.example .env.staging
      cp .env.example .env.production

[ ] Fill in OPENAI_API_KEY with your real key

[ ] Generate a strong JWT secret:
      python -c "import secrets; print(secrets.token_hex(32))"
      → paste result into JWT_SECRET_KEY

[ ] Set POSTGRES_PASSWORD to something strong (not "mypassword")

[ ] Fill in LANGFUSE_PUBLIC_KEY and LANGFUSE_SECRET_KEY from langfuse.com

[ ] Set APP_ENV correctly (development / staging / production)

[ ] Set DEBUG=false for staging and production

[ ] Set ALLOWED_ORIGINS to your actual frontend URL(s)

[ ] Set LOG_LEVEL=WARNING and LOG_FORMAT=json for production
```

---

## 11. Security Rules — Never Break These

> ⚠️ These are non-negotiable. Breaking them can cause data breaches or account takeovers.

1. **Never commit `.env`, `.env.development`, `.env.staging`, `.env.production`** to git.
   Add them to `.gitignore`:
   ```
   .env
   .env.*
   !.env.example
   ```

2. **Never use weak `JWT_SECRET_KEY`** like `"secret"` or `"password"` — always use a cryptographically random key.

3. **Never set `DEBUG=true` in production** — it exposes internal errors to end users.

4. **Never hardcode secrets** in `config.py` or any Python file. Always use env vars.

5. **Rotate `LANGFUSE_SECRET_KEY` and `JWT_SECRET_KEY`** periodically, especially if you suspect they've been leaked.

6. **Use separate keys for each environment** — development keys should never work in production.

---

*Last updated: July 2026 | Based on `.env.example` of the `7_layers_production_agentic_ai` project*
