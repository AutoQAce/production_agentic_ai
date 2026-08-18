# ⚙️ `app/core/config.py` — Line-by-Line Guide

> **Purpose:** A personal reference covering **every line** of this project's settings module.
> For each line: what it means in plain English, **what breaks if you don't write it**, the technical
> mechanism, why *this* way and not the obvious alternatives, and where it fits in a production
> agentic AI system.
>
> **Written:** 2026-08-16, after replacing the article's hand-rolled `os.getenv` config with this one.
> **Companion docs:** [`1_env_guide.md`](./1_env_guide.md) explains *what each variable means*.
> This guide explains *how they get loaded, validated, and guarded*.

---

## 🚨 Read this first — the three bugs this rewrite fixed

The version of `config.py` this replaced looked fine and was broken in three ways. Every design
decision below exists because of one of them:

| # | Bug | Symptom |
|---|---|---|
| 1 | `Settings` had no `LOG_LEVEL` / `LOG_FORMAT` | **The app did not boot.** `configure_logging(settings)` raised `AttributeError: 'Settings' object has no attribute 'LOG_FORMAT'` |
| 2 | Secrets were plain `str` | `repr(settings)`, a traceback, or `logger.info(settings)` would print your OpenAI key and DB password straight into the log pipeline |
| 3 | Every secret had a default | `JWT_SECRET_KEY = ""` meant **production would boot happily and sign auth tokens with an empty secret**. Nothing would tell you. |

**The meta-lesson:** config bugs don't announce themselves. A wrong `.env` value doesn't crash — it
runs *slightly wrong* for six months. The whole job of this file is to convert "silently wrong" into
"loudly refuses to start."

---

## 📚 Table of Contents

| § | Section | Lines |
|---|---|---|
| 1 | [What this file is, and the one idea behind it](#1-what-this-file-is) | — |
| 2 | [Module docstring — the contract](#2-module-docstring--the-contract) | 1–25 |
| 3 | [Imports](#3-imports--lines-2739) | 27–39 |
| 4 | [`PROJECT_ROOT`](#4-project_root--lines-4143) | 41–43 |
| 5 | [`DeploymentTier` — name vs. policy](#5-deploymenttier--lines-4656) | 46–56 |
| 6 | [`ENVIRONMENT_TIERS` — the OCP trick](#6-environment_tiers--lines-5975) | 59–75 |
| 7 | [The three module constants](#7-the-three-module-constants--lines-7784) | 77–84 |
| 8 | [`_current_app_env()` — the chicken-and-egg](#8-_current_app_env--lines-8793) | 87–93 |
| 9 | [`_env_files()` — precedence ladder](#9-_env_files--lines-96107) | 96–107 |
| 10 | [`_is_placeholder()`](#10-_is_placeholder--lines-110113) | 110–113 |
| 11 | [`model_config` — the five flags](#11-model_config--lines-124130) | 124–130 |
| 12 | [The fields](#12-the-fields--lines-132167) | 132–167 |
| 13 | [Field validators — normalisation](#13-field-validators--lines-169179) | 169–179 |
| 14 | [Properties — derived values](#14-properties--lines-181204) | 181–204 |
| 15 | [`_validate_startup_policy` — the guard](#15-_validate_startup_policy--lines-206254) | 206–254 |
| 16 | [`get_settings()` — the injection seam](#16-get_settings--lines-257265) | 257–265 |
| 17 | [SOLID scorecard](#17-solid-scorecard) | — |
| 18 | [Where this fits in the 7 layers](#18-where-this-fits-in-the-7-layers) | — |
| 19 | [How to extend it](#19-how-to-extend-it) | — |
| 20 | [Cheat sheet](#20-cheat-sheet) | — |

---

## 1. What this file is

🍕 **Plain terms:** it is the **reception desk** of the application. Nothing gets into the building
without passing through it. Every API key, database password, log level, and feature flag comes from
the outside world (a `.env` file, a Docker `-e` flag, a Kubernetes secret) and has to be **checked at
the desk** before any code is allowed to use it.

A bad reception desk lets anyone walk in wearing a fake badge. A good one checks the badge, refuses
entry if it's a photocopy, and does it **once at 9am** — not on every single visit.

🔧 **Technical:** it converts untyped, unvalidated `str` environment variables into one frozen,
fully-typed, validated `Settings` object, and refuses to construct that object at all if the
configuration is unsafe for the environment it claims to be.

### The one idea behind the whole file

> **Fail at startup, not at 3am.**

Every design choice below is downstream of that sentence. A misconfigured process should die in the
first second of its life — while the deploy pipeline is watching and can roll back — not three hours
later when a user hits the one endpoint that touches the missing key.

---

## 2. Module docstring — the contract

```python
"""Settings management — Layer 0 (Foundation).

One concrete `Settings` class, loaded once and cached. Consumers do **not** import it directly;
they declare the narrow `Protocol` they need (see `LoggingConfig` in `logging.py`) and receive a
`Settings` that structurally satisfies it. ...
"""
```

🍕 **Plain terms:** the note taped to the front of the reception desk explaining the rules to whoever
staffs it next — including future-you.

🔧 **Technical:** four things are documented because they're the four things a reader would otherwise
have to reverse-engineer: the DIP/ISP shape, how environments work, the precedence order, and where
cloud secret stores plug in later.

❓ **What if we don't write it:** nothing breaks — but in three months you'll open this file, see
`ENVIRONMENT_TIERS` and `_env_files` and `_current_app_env` and not know which one drives which. The
docstring is the map.

> **The transferable idea:** document **the decisions**, not the code. `PROJECT_ROOT = Path(...)`
> needs no comment. "Resolved from `__file__`, not the CWD" does — because that's a *choice*, and a
> choice can be silently undone by a well-meaning refactor.

---

## 3. Imports — lines 27–39

```python
from __future__ import annotations

import logging
import os
from enum import StrEnum
from functools import lru_cache
from pathlib import Path
from urllib.parse import quote_plus

from pydantic import Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from app.core.exceptions import ConfigurationError
```

### `from __future__ import annotations`

🍕 **Plain terms:** "don't evaluate my type hints right now, just remember them as text."

🔧 **Technical:** makes all annotations lazy strings (PEP 563). Here it does one concrete job: it
lets `_validate_startup_policy(self) -> Settings` name the class **from inside the class body**,
where `Settings` doesn't exist yet.

❓ **What if we don't write it:** `NameError: name 'Settings' is not defined` at import time. You'd
have to write `-> "Settings"` in quotes instead.

### `import logging`

Used exactly once, at line 223: `logging.getLevelNamesMapping()`.

🍕 **Plain terms:** instead of writing our own list of valid log levels, we ask Python's logging
module "what levels do you actually know about?"

🔧 **Technical:** `getLevelNamesMapping()` (Python 3.11+) returns `{"DEBUG": 10, "INFO": 20, ...}`
including any custom level someone registered with `logging.addLevelName()`.

❓ **Why this way only:** the obvious alternative is
`if self.LOG_LEVEL not in {"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"}`. That hardcoded set is a
**second source of truth**. The day someone adds a `TRACE` level for agent step logging, the config
rejects it and nobody knows why. Asking the library is always better than duplicating the library.

### `import os`

Only for `os.getenv("APP_ENV")` at line 93 — see [§8](#8-_current_app_env--lines-8793) for why that
one read has to happen outside pydantic.

### `from enum import StrEnum`

🔧 **Technical:** Python 3.11+. `StrEnum` members **are** strings, so `DeploymentTier.PRODUCTION ==
"production"` is `True` and `str(tier)` gives `"production"` — which matters at line 233 where we put
the tier into a log context dict that must be JSON-serialisable.

❓ **Why not plain `Enum`:** `str(SomeEnum.X)` gives `"SomeEnum.X"` and JSON serialisation fails.
`StrEnum` gives you type safety *and* free serialisation.

### `from functools import lru_cache`

The entire caching strategy, in one stdlib decorator. See [§16](#16-get_settings--lines-257265).

### `from pathlib import Path`

Used to build absolute `.env` paths. See [§4](#4-project_root--lines-4143).

### `from urllib.parse import quote_plus`

🍕 **Plain terms:** a password like `p@ss/word` has characters that mean something special inside a
URL. `quote_plus` turns them into safe codes (`p%40ss%2Fword`).

🔧 **Technical:** percent-encoding for the userinfo section of the DSN.

❓ **What if we don't write it:** `postgresql://user:p@ss/word@db:5432/mydb` — the driver sees the
**first** `@` as the host separator and tries to connect to a host called `ss/word@db`. You get a
baffling DNS error that looks nothing like "your password has an @ in it." **This is a real,
common, hours-of-debugging production bug**, and it costs one stdlib function to make impossible.

### The pydantic imports

| Import | Job |
|---|---|
| `Field` | attach constraints (`ge=`, `le=`) and `default_factory` to a field |
| `SecretStr` | a string that refuses to print itself |
| `field_validator` | normalise **one field** before/after parsing |
| `model_validator` | validate **the whole object** once all fields are set |
| `BaseSettings` | the pydantic-settings base that knows how to read env vars and `.env` files |
| `SettingsConfigDict` | the typed config dict for `BaseSettings` |

### `from app.core.exceptions import ConfigurationError`

🍕 **Plain terms:** when config is wrong we raise *our* error type, not a generic one.

🔧 **Technical:** `ConfigurationError` is an `AppException` subclass carrying `error_code`,
`http_status_code`, and a structured `log_context()`. Raising it means the failure arrives in logs as
structured fields (`known_environments=[...]`, `valid_levels=[...]`) rather than a prose string.

❓ **Why this way only:** pydantic wraps `ValueError` into a long `ValidationError` traceback. A
`ConfigurationError` propagates **as-is** — so a bad deploy prints one clean line telling you exactly
which variable is wrong and what the valid options are, instead of forty lines of pydantic internals.

> ⚠️ **Import-direction note:** `config.py` imports from `exceptions.py`, never the reverse.
> `exceptions.py` is pure data with zero dependencies, which is why it can sit underneath everything.

---

## 4. `PROJECT_ROOT` — lines 41–43

```python
# app/core/config.py -> app/core -> app -> <project root>. Resolved from __file__, not the CWD,
# so `.env` discovery does not depend on where uvicorn/pytest was launched from.
PROJECT_ROOT = Path(__file__).resolve().parents[2]
```

🍕 **Plain terms:** "find the project's front door by walking up from where *this file* lives" —
not by asking "what folder am I standing in right now?"

🔧 **Technical:** `__file__` is `.../app/core/config.py`. `.resolve()` makes it absolute and follows
symlinks. `.parents[2]` walks up three levels: `[0]` = `app/core`, `[1]` = `app`, `[2]` = repo root.

❓ **What if we don't write it (i.e. use relative `".env"`):** relative paths resolve against the
**current working directory**. Then:

```
cd C:\Bhavya\Medium\production_agentic_ai
uv run uvicorn app.main:app          # ✅ finds .env

cd C:\Bhavya\Medium
uv run uvicorn ...                   # ❌ silently finds nothing, all defaults
docker run ... (WORKDIR /code)       # ❌ or ✅ depending on the Dockerfile
systemd service (WorkingDirectory=/) # ❌ silently finds nothing
```

The failure mode is the worst kind: **no error**. Every setting quietly falls back to its default,
your app connects to `db:5432` with password `mypassword`, and you spend an afternoon on it.

❓ **Why this way only:** the alternative is `os.path.dirname(os.path.dirname(os.path.dirname(__file__)))`
— which is what the article's version did. Same result, unreadable, and it doesn't `.resolve()`, so
symlinked deployments (very common with Docker layer caching and CI checkouts) break.

⚠️ **Maintenance trap:** `parents[2]` is coupled to this file's depth. If `config.py` ever moves to
`app/core/settings/config.py`, this must become `parents[3]`. That's what the comment on line 41 is
protecting.

---

## 5. `DeploymentTier` — lines 46–56

```python
class DeploymentTier(StrEnum):
    """The *policy* class of an environment — what the startup guard enforces. ..."""

    DEVELOPMENT = "development"
    TEST = "test"
    STAGING = "staging"
    PRODUCTION = "production"
```

🍕 **Plain terms:** this is the **security clearance level**, not the room name.

Your company has rooms called `dev`, `sit`, `uat`, `preprod`, `perf`, `prod`. But it only has a
handful of *rulebooks*: "anything goes," "test data only," "real infrastructure — no placeholders,"
and "customer data — maximum lockdown." `DeploymentTier` is the rulebook. `APP_ENV` is the room.

🔧 **Technical:** a four-member `StrEnum`. Every branch in the startup guard tests against this, never
against a raw string.

### ❓ Why separate the room from the rulebook?

This is **the single most important design decision in the file**, so here it is spelled out.

The article's version had one concept: an `Environment` enum with four members. That means:

```
Your company spins up a "sit" environment.
  → "sit" is not in the Environment enum
  → you must edit config.py, add SIT = "sit"
  → you must then edit apply_environment_settings() to add a SIT branch
  → you must decide, in Python code, what SIT's log level and rate limits are
  → deploy code to change a rate limit
```

That's the **Open/Closed Principle violation** — every new environment forces edits to existing,
tested code. And it's a real constraint for you specifically, because you asked for dev/uat/sit/etc.

With the split:

```
Your company spins up a "sit" environment.
  → add one row to ENVIRONMENT_TIERS: "sit": DeploymentTier.STAGING
  → create .env.sit with its values
  → done. The guard never changed. No branch was added anywhere.
```

The guard code is **closed for modification** (you never touch the `if` statements) but the system is
**open for extension** (new environments are new data rows and new files).

### ❓ Why four tiers and not three, or six?

Each tier exists because at least one rule differs:

| Tier | What's different about it |
|---|---|
| `DEVELOPMENT` | Placeholder secrets are **fine**. `.env.example` defaults must boot, or onboarding is miserable. |
| `TEST` | Same leniency, but semantically distinct — CI may later want different behaviour (no external calls, fake LLM) |
| `STAGING` | Real infrastructure. Real secrets required, `DEBUG=false`. But it's not customer-facing, so a short JWT secret and wildcard CORS are tolerable. |
| `PRODUCTION` | Everything STAGING requires **plus** no wildcard CORS and a ≥32-char JWT secret. |

If two tiers ever end up with identical rules, merge them. A tier that changes nothing is dead code.

🎯 **Where it fits in an agentic AI system:** agents call paid APIs and write to shared memory
stores. The tier is what will later decide *"is this run allowed to hit the real OpenAI billing
account and the real vector DB, or the sandbox ones?"* Getting the tier concept right at Layer 0 is
what makes that a one-line check later instead of a refactor.

---

## 6. `ENVIRONMENT_TIERS` — lines 59–75

```python
# APP_ENV value -> policy tier. Data, not branches: a new environment is one row here.
# Unknown names are rejected at startup rather than silently defaulting to a lax tier.
ENVIRONMENT_TIERS: dict[str, DeploymentTier] = {
    "local": DeploymentTier.DEVELOPMENT,
    "dev": DeploymentTier.DEVELOPMENT,
    "development": DeploymentTier.DEVELOPMENT,
    "test": DeploymentTier.TEST,
    "ci": DeploymentTier.TEST,
    "sit": DeploymentTier.STAGING,
    "uat": DeploymentTier.STAGING,
    "qa": DeploymentTier.STAGING,
    "stage": DeploymentTier.STAGING,
    "staging": DeploymentTier.STAGING,
    "preprod": DeploymentTier.STAGING,
    "prod": DeploymentTier.PRODUCTION,
    "production": DeploymentTier.PRODUCTION,
}
```

🍕 **Plain terms:** the **badge-to-clearance lookup table** at reception. Thirteen badge names, four
clearance levels. Adding a fourteenth badge is writing one line in the table — you don't retrain the
security guard.

🔧 **Technical:** a module-level `dict` mapping the free-form `APP_ENV` string to a policy tier.
Deliberately module-level (not a class attribute, not inside a function) so that tests, tooling, and
future code can read it, and so the error message at line 217 can list every valid name.

### ❓ Why a dict instead of `match`/`if-elif`?

The article used:

```python
match os.getenv("APP_ENV", "development").lower():
    case "production" | "prod": return Environment.PRODUCTION
    case "staging" | "stage":   return Environment.STAGING
    ...
    case _:                     return Environment.DEVELOPMENT
```

Three problems, in order of severity:

1. **`case _: return DEVELOPMENT` fails *open*.** Typo `APP_ENV=prodction` in your production
   deploy manifest, and the app **starts in development mode in production** — debug on, verbose
   logs, all guards skipped. This is a genuine security incident waiting to happen. Our dict has no
   fallback; an unknown name raises at line 215.
2. **Branches can't be inspected.** You can't ask a `match` statement "what are all your valid
   inputs?" You *can* ask a dict: `sorted(ENVIRONMENT_TIERS)` — which is exactly what the error
   message does, so the operator sees the valid list at the moment they need it.
3. **Adding an environment means editing logic.** Editing data is safe; editing control flow means
   re-reading and re-testing the branch structure.

> **The transferable idea:** **prefer data over branches.** When a decision is a lookup, write a
> lookup. Branches are for decisions that genuinely differ in *behaviour*, not in *value*.

❓ **What if we don't include aliases like `prod` and `dev`:** somebody's Kubernetes manifest says
`APP_ENV=prod` (very common), and the app refuses to start. Aliases cost one line each and remove a
whole class of deploy-day friction. This is being liberal in what you accept — but *only* from a
closed list.

---

## 7. The three module constants — lines 77–84

```python
# Tiers that run on shared infrastructure and must never boot on `.env.example` defaults.
_STRICT_TIERS = frozenset({DeploymentTier.STAGING, DeploymentTier.PRODUCTION})

# Literal placeholders shipped in `.env.example`. Anything starting with "your-" is caught too,
# which covers the rest of that file without listing every key.
_PLACEHOLDER_SECRETS = frozenset({"change-me", "changeme", "secret", "password", "mypassword", "postgres"})

_MIN_PRODUCTION_SECRET_LENGTH = 32
```

### `_STRICT_TIERS`

🍕 **Plain terms:** "which clearance levels get the full pat-down."

🔧 **Technical:** a `frozenset` for O(1) membership. Used once, at line 229:
`if tier not in _STRICT_TIERS: return self` — a single early-exit that separates "environments where
a human is watching" from "environments where nobody is."

❓ **Why `frozenset` and not a `set` or `tuple`:** `frozenset` is immutable, so no code anywhere can
accidentally `add()` to it at runtime and weaken your security posture. It's also hashable and
O(1) — `tuple` membership is O(n). Two characters of typing for a guarantee.

❓ **Why a named constant instead of `if tier in (STAGING, PRODUCTION)` inline:** because the name
carries the *reason*. `_STRICT_TIERS` tells a reader why those two are grouped; an inline tuple
doesn't. And when `PERF` gets added later, there's exactly one place to add it.

### `_PLACEHOLDER_SECRETS`

🍕 **Plain terms:** the list of "obviously fake" passwords. If your production database password is
literally `mypassword`, you didn't set a password.

🔧 **Technical:** checked case-insensitively at line 113, alongside a `startswith("your-")` rule.

❓ **Why the `your-` prefix rule instead of listing every key:** open [`.env.example`](../.env.example)
— it uses `"your-llm-api-key"`, `"your-jwt-secret-key"`, `"your-langfuse-secret-key"`. One prefix
rule catches the entire family, **including keys that don't exist yet**. When you add
`ANTHROPIC_API_KEY="your-anthropic-key"` to `.env.example` next month, the guard already covers it
with zero changes.

❓ **What if we don't write this at all:** the guard would only catch *empty* secrets. Somebody
copies `.env.example` → `.env.production`, fills in the OpenAI key, forgets the JWT one, deploys.
The app boots. Every auth token in production is signed with the string `"change-me"`. Anyone who
has ever read this public repo template can forge an admin token.

### `_MIN_PRODUCTION_SECRET_LENGTH = 32`

🍕 **Plain terms:** "a real key, not a word."

🔧 **Technical:** 32 characters. HS256 (this project's `JWT_ALGORITHM`) uses HMAC-SHA256, whose
security is bounded by key entropy; RFC 7518 §3.2 requires a key of at least 256 bits (32 bytes) for
HS256. `python -c "import secrets; print(secrets.token_hex(32))"` gives you 64 hex chars — comfortably
over.

❓ **Why a named constant and not the literal `32` inline:** it appears in two places — the check at
line 248 and the error's `minimum_length=` context at line 251. A magic number in two places is a
future inconsistency.

⚠️ **Known limitation:** length is a proxy for entropy, not a measure of it.
`"aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa"` passes. A real entropy check (`zxcvbn`, or a Shannon entropy
floor) would be stricter — but that's a dependency for a guard that already catches 99% of real
mistakes. Noted here so future-you knows it was a deliberate stopping point, not an oversight.

---

## 8. `_current_app_env()` — lines 87–93

```python
def _current_app_env() -> str:
    """Read `APP_ENV` from the *process* environment.

    Deliberately not read from a `.env` file: this value chooses which file to load, so it has to
    be known before any file is parsed. Setting `APP_ENV` inside `.env.production` cannot work.
    """
    return os.getenv("APP_ENV", "development").strip().lower()
```

🍕 **Plain terms:** before you can open the right filing cabinet, you have to know **which cabinet**.
And that answer can't be *inside* the cabinet.

🔧 **Technical:** this is the one genuine chicken-and-egg problem in the file. `APP_ENV` determines
which `.env.*` files pydantic-settings loads — and `model_config` is evaluated at **class-definition
time**, before any instance exists and before any file is read. So this single value must come from
the raw process environment via `os.getenv`.

❓ **Why `.strip().lower()`:** three real-world sources of whitespace and case:
- YAML: `APP_ENV: "production "` — trailing space from a copy-paste
- Windows: `set APP_ENV=Production` — people capitalise
- CI: `APP_ENV=PROD` in a GitHub Actions matrix

Without normalisation, `"Production"` isn't in `ENVIRONMENT_TIERS` and the app refuses to start with
a confusing message. Normalising costs 15 characters.

❓ **Why a function instead of a module-level `_APP_ENV = os.getenv(...)` constant:** because it's
used **twice, at two different times**:
1. Line 125, at class-definition time, to pick the env files.
2. Line 133, as `default_factory`, at **instance-construction** time.

A module-level constant would freeze the value at import. `default_factory` re-reads it on every
`Settings()` construction — which is exactly what makes
`monkeypatch.setenv("APP_ENV", "test"); get_settings.cache_clear()` work in tests.

> ⚠️ **The one wart, documented honestly:** `env_file` is fixed at class-definition time, so if you
> monkeypatch `APP_ENV` in a test, the *field* updates but the *file list* doesn't. This doesn't
> matter here (tests pass `_env_file=None`), but it's the reason the docstring says `APP_ENV` must
> come from the process environment. Putting `APP_ENV=production` inside `.env.production` will set
> the field but will **not** cause that file to load — it's already too late.

🎯 **Where it fits:** in Docker/Kubernetes, `APP_ENV` comes from the container spec
(`environment: APP_ENV=production` in `docker-compose.yml`), never from a file. This function is the
seam between "how the platform tells us who we are" and "how we configure ourselves."

---

## 9. `_env_files()` — lines 96–107

```python
def _env_files(app_env: str) -> tuple[Path, ...]:
    """Env files in ascending precedence — later entries win, absent entries are skipped. ..."""
    return (
        PROJECT_ROOT / ".env",
        PROJECT_ROOT / ".env.local",
        PROJECT_ROOT / f".env.{app_env}",
        PROJECT_ROOT / f".env.{app_env}.local",
    )
```

🍕 **Plain terms:** a stack of transparencies on an overhead projector. The bottom sheet has the
company-wide defaults. Each sheet on top overwrites just the bits it cares about. What you see is
the combination, with the **top sheet winning**.

🔧 **Technical:** pydantic-settings accepts a tuple for `env_file` and applies them **left to right,
later files overriding earlier ones**. Non-existent files are skipped silently — no error.

### The full precedence ladder (lowest → highest)

```
1. Field defaults in Settings          POSTGRES_HOST: str = "db"
2. .env                                shared across all environments
3. .env.local                          your machine, all environments  (gitignored)
4. .env.<app_env>                      e.g. .env.production — the deploy provides this
5. .env.<app_env>.local                your machine, this environment (gitignored)
6. Real process environment            docker -e / k8s secret / export
7. Direct kwargs: Settings(DEBUG=True) tests only
```

❓ **Why does `.env.<app_env>` beat `.env.local`?** Because `.env.local` is your *personal* baseline
("always use my local Postgres"), while `.env.production` is a *deliberate environment choice*. If
you explicitly run with `APP_ENV=production`, the production file should win over your personal
default. Then `.env.production.local` exists for the rare "I need to poke at production config
locally with one value changed" case, and sits on top of everything.

❓ **Why do real env vars beat every file?** Because that's how containers work. Kubernetes injects
secrets as environment variables; Docker Compose uses `environment:`. If a file could override an
injected secret, a stale `.env` accidentally baked into an image would silently override the real
secret from your vault. Files are defaults; the platform is truth.

❓ **What if we don't have the `.local` tiers:** every developer either edits the shared `.env`
(and risks committing it) or maintains a private patch. The `.local` convention — which Next.js,
Vite, Rails, and Laravel all use — gives everyone a personal override slot that's gitignored by
default. Confirmed in this repo: [`.gitignore`](../.gitignore) has `.env.*` with `!.env.example`,
so all four tiers are already protected.

❓ **Why return `tuple[Path, ...]` and not `list[str]`:**
- `tuple` → immutable, signals "this is a fixed sequence, not a collection you append to"
- `Path` → `PROJECT_ROOT / ".env"` is OS-agnostic; string concatenation with `/` breaks on Windows
  and `os.path.join` is noisier

---

## 10. `_is_placeholder()` — lines 110–113

```python
def _is_placeholder(secret: SecretStr) -> bool:
    """True when a secret is empty or still holds an example/scaffold value."""
    value = secret.get_secret_value().strip().lower()
    return not value or value in _PLACEHOLDER_SECRETS or value.startswith("your-")
```

🍕 **Plain terms:** "is this a real key, or did somebody just copy the example file and hit deploy?"

🔧 **Technical:** three checks, ordered cheapest-first:

| Check | Catches |
|---|---|
| `not value` | `OPENAI_API_KEY=` or unset entirely (`""` default) |
| `value in _PLACEHOLDER_SECRETS` | `change-me`, `mypassword`, `postgres`, `secret` |
| `value.startswith("your-")` | the whole `.env.example` family, present and future |

❓ **Why a module-level function instead of a method on `Settings`:** it doesn't touch `self`. A
free function is testable in isolation, reusable by any future module (a `/health/config` endpoint,
a pre-deploy CLI check), and keeps `Settings` focused on *being* settings rather than *judging*
them. **Single Responsibility, applied at the function level.**

❓ **Why does it take `SecretStr` and not `str`:** so the type system forces you to call it on an
actual secret field. Passing `settings.POSTGRES_HOST` (a plain `str`) is a type error, which is
correct — a hostname being `"your-host"` is not a security problem.

⚠️ **Note the `.get_secret_value()`:** this is the *one place* the file deliberately unwraps a
secret, and it's for a check that never logs the value. Every unwrap in this codebase should be
this obvious.

---

## 11. `model_config` — lines 124–130

```python
model_config = SettingsConfigDict(
    env_file=_env_files(_current_app_env()),
    env_file_encoding="utf-8",
    extra="ignore",
    case_sensitive=True,
    frozen=True,
)
```

🍕 **Plain terms:** the reception desk's own operating manual — which drawers to check, what alphabet
they're written in, what to do with unknown paperwork, and whether anyone can rewrite the register
after 9am.

Five flags, each preventing a specific problem:

### `env_file=_env_files(_current_app_env())`

Evaluated **once, at class-definition time** (i.e. when `config.py` is first imported). See
[§8](#8-_current_app_env--lines-8793) for why it has to be.

### `env_file_encoding="utf-8"`

❓ **What if we don't write it:** pydantic-settings falls back to the platform default encoding. On
Windows that can be `cp1252`. A `.env` containing a non-ASCII character — an accented name in
`PROJECT_NAME`, a `£` or `€` in a description, a smart quote pasted from a doc — raises
`UnicodeDecodeError` **on Windows only**. Classic "works on my machine, breaks in CI" (or the
reverse). Six words of config removes an entire cross-platform failure mode.

### `extra="ignore"`

🍕 **Plain terms:** "if the `.env` file mentions something I don't have a slot for, don't panic."

🔧 **Technical:** three options exist — `"ignore"` (drop it), `"forbid"` (raise), `"allow"` (attach
it dynamically).

❓ **Why `"ignore"` here, specifically:** [`.env.example`](../.env.example) declares
`RATE_LIMIT_DEFAULT`, `RATE_LIMIT_CHAT`, `RATE_LIMIT_CHAT_STREAM`, `RATE_LIMIT_MESSAGES`,
`RATE_LIMIT_LOGIN` — and none of them have fields yet, because **SlowAPI isn't wired into
`main.py` yet**. With `"forbid"`, the app would refuse to boot on a legitimate `.env` file.

⚠️ **The cost, stated plainly:** `"ignore"` also swallows **typos**. Write `OPENAI_APIKEY=sk-...`
(missing underscore) in `.env.production` and the app boots using the empty default — until the
strict-tier guard catches that one. But a typo'd `LOG_LEVL=WARNING` gets no such protection; you'd
silently run at `INFO`.

✅ **The plan:** flip to `"forbid"` the moment every key in `.env.example` has a field. That's Layer 2
(rate limiting) work. This is a **deliberate, dated trade-off**, not an oversight.

### `case_sensitive=True`

🍕 **Plain terms:** `APP_ENV` and `app_env` are different variables. Pick one and mean it.

🔧 **Technical:** by default pydantic-settings matches env var names case-insensitively. With
`True`, the field name must match the env var exactly.

❓ **Why:** environment variables are conventionally `SCREAMING_SNAKE_CASE`, and this project's
fields are named to match 1:1. Case-insensitive matching means a stray lowercase `debug=true` in
someone's shell could set `DEBUG` — an invisible action-at-a-distance. Exact matching makes the
mapping between `.env.example` and this file mechanically checkable by eye.

### `frozen=True`

🍕 **Plain terms:** once the register is written at 9am, **nobody edits it**. Not the front desk, not
a manager, not a request handler at 2pm.

🔧 **Technical:** any `settings.X = y` raises `ValidationError`. Verified by
`test_settings_are_frozen`.

❓ **What problem does this solve — concretely:** the article's version had this:

```python
for key, value in current_env_settings.items():
    setattr(self, key, value)     # ← mutating settings after construction
```

Mutable settings in an async server is a genuine correctness bug: request A mutates `settings.DEBUG`,
requests B through Z (running concurrently on the same event loop) see the changed value. There is no
lock and no ownership. Debugging that is miserable because the bug depends on request timing.

`frozen=True` makes the entire class of bug impossible at the type level. It also aligns with the
project's immutability rule and makes `Settings` hashable and safely shareable across threads and
tasks — which matters when LangGraph fans out parallel agent branches.

> 🎯 **Agentic AI angle:** in a graph with parallel nodes, several agent branches read config
> simultaneously. Frozen settings means no branch can observe a half-updated config, and no branch
> can "helpfully" bump `MAX_LLM_CALL_RETRIES` for everyone else.

---

## 12. The fields — lines 132–167

```python
# --- Application ---
APP_ENV: str = Field(default_factory=_current_app_env)
PROJECT_NAME: str = "7 Layers Production Agentic AI"
VERSION: str = "0.1.0"
DEBUG: bool = True
```

🍕 **Plain terms:** the actual form fields on the reception desk. Each line declares a name, a type,
and what to assume if nobody fills it in.

🔧 **Technical:** every field here does **four** jobs at once, which is the whole reason for using
pydantic instead of `os.getenv`:

```python
POSTGRES_PORT: int = Field(default=5432, ge=1, le=65535)
#              │              │           └────────────── 4. CONSTRAINT — valid range
#              │              └────────────────────────── 3. DEFAULT    — if unset
#              └───────────────────────────────────────── 2. TYPE       — parse "5432" → 5432
#  └──────────────────────────────────────────────────── 1. NAME        — the env var to read
```

Compare to the article's `int(os.getenv("POSTGRES_PORT", "5432"))`: that does 1–3 but not 4, and
when it fails you get a bare `ValueError: invalid literal for int()` with **no mention of which
variable**. Pydantic tells you the field name, the bad value, and the rule it broke.

### `APP_ENV: str = Field(default_factory=_current_app_env)`

❓ **Why `default_factory` and not `default=_current_app_env()`:** `default=` evaluates **once at
import**; `default_factory=` evaluates **on every construction**. The latter is what makes tests
able to change the environment and rebuild. Getting this backwards is a subtle and common bug.

❓ **Why `str` and not `DeploymentTier`:** deliberate — this is the *room name*, free-form to support
`sit`/`uat`/`perf`. The *rulebook* is the derived `tier` property. See [§5](#5-deploymenttier--lines-4656).

### `DEBUG: bool = True`

❓ **Why default to `True`, which is the "unsafe" value?** Because the default serves **development**
— clone the repo, run it, get useful errors. Production safety doesn't come from a cautious default
(anyone can override a default); it comes from the **guard at line 232** that refuses to start a
strict-tier process with `DEBUG=True`. Defaults are for convenience; guards are for safety. Don't
try to make defaults do the guard's job.

### `ALLOWED_ORIGINS: str = "http://localhost:3000,http://localhost:8000"`

❓ **Why `str` and not `list[str]`:** pydantic-settings tries to **JSON-decode** complex types from
env vars. `ALLOWED_ORIGINS=a,b` isn't valid JSON, so a `list[str]` field would raise `SettingsError`
on a perfectly reasonable value. You'd have to write `ALLOWED_ORIGINS=["a","b"]` in `.env` — ugly,
and inconsistent with how everyone else writes env vars. Keeping it a `str` and exposing a parsed
`allowed_origins_list` property ([§14](#14-properties--lines-181204)) is the smaller, more
conventional solution.

### The logging fields — lines 142–144

```python
# --- Logging (consumed via the `LoggingConfig` Protocol in app/core/logging.py) ---
LOG_LEVEL: str = "INFO"
LOG_FORMAT: str = "json"  # validated by `_tail_processors_for()`, which owns the renderer registry
```

🚨 **These two lines are the boot-crash fix.** [`logging.py`](../app/core/logging.py) declares:

```python
@runtime_checkable
class LoggingConfig(Protocol):
    LOG_LEVEL: str
    LOG_FORMAT: str
    PROJECT_NAME: str
    VERSION: str
    APP_ENV: str
```

and `main.py` calls `configure_logging(settings)`. Without these fields, `Settings` doesn't satisfy
the Protocol and you get `AttributeError` before the first request.

> ⚠️ **Updated 2026-08-19:** this Protocol was 2 fields when this guide was written. It is now **5** —
> `PROJECT_NAME`/`VERSION`/`APP_ENV` were added so every log line carries service identity. See
> [`4_logging_guide.md` §5](./4_logging_guide.md#5-loggingconfig--lines-3749).

❓ **Why is `LOG_FORMAT` not validated here:** because `logging.py` already owns the renderer
registry (`_TAIL_PROCESSORS`) and raises `ConfigurationError` with the valid list. Validating it
*here too* would create a second source of truth that drifts the moment someone registers a new
renderer. **Whoever owns the registry owns the validation.**

❓ **Why is `LOG_LEVEL` validated here then?** Because nobody else does. `logging.setLevel("CHATTY")`
raises a `ValueError` from deep inside stdlib with no useful context. We catch it at the boundary.

> **The transferable idea:** validate at the boundary **closest to the knowledge**. Config validates
> what only config knows; the logging module validates what only it knows. Duplicated validation is
> worse than none, because the two copies will disagree.

### `SecretStr` fields — lines 147, 153, 162, 166

```python
OPENAI_API_KEY: SecretStr = SecretStr("")
JWT_SECRET_KEY: SecretStr = SecretStr("change-me")
POSTGRES_PASSWORD: SecretStr = SecretStr("mypassword")
LANGFUSE_SECRET_KEY: SecretStr = SecretStr("")
```

🍕 **Plain terms:** a `SecretStr` is a **sealed envelope**. You can pass it around, store it, put it
in a dict — and it always shows `**********` on the outside. Only `.get_secret_value()` opens it,
and that's a visible line of code somebody can grep for.

🔧 **Technical:** `repr(SecretStr("sk-abc"))` → `SecretStr('**********')`. Verified by
`test_secrets_do_not_leak_through_repr`.

❓ **What if we don't write this — the concrete scenario:**

```python
logger.info("starting", config=settings)   # someone adds this for debugging
```

With plain `str`, that line ships your OpenAI key, database password, and JWT signing key **into your
log aggregator** — where they're indexed, replicated, retained for 90 days, and visible to everyone
with log access. The same thing happens automatically in any unhandled exception traceback that
includes `settings` in a frame's locals.

This is not hypothetical; it is one of the most common ways real production secrets leak. `SecretStr`
makes it structurally impossible.

🎯 **Agentic AI angle:** this matters *more* here than in a normal web app. LangSmith and Langfuse
capture full call traces including inputs. An agent config accidentally serialised into a trace goes
straight to a third-party SaaS dashboard. `SecretStr` survives that trip sealed.

❓ **Why is `LANGFUSE_PUBLIC_KEY` a plain `str` (line 165):** because it's public by design — it
identifies your project, like a username. Marking non-secrets as secret is its own problem: it
trains people to call `.get_secret_value()` reflexively, which defeats the purpose.

### `Field(...)` constraints — lines 149, 150, 155, 161

```python
DEFAULT_LLM_TEMPERATURE: float = Field(default=0.0, ge=0.0, le=2.0)
MAX_LLM_CALL_RETRIES: int = Field(default=3, ge=0)
JWT_ACCESS_TOKEN_EXPIRE_DAYS: int = Field(default=30, ge=1)
POSTGRES_PORT: int = Field(default=5432, ge=1, le=65535)
```

🍕 **Plain terms:** the form doesn't just ask for a number, it says "between 1 and 65535."

| Constraint | What it prevents |
|---|---|
| `TEMPERATURE ge=0.0, le=2.0` | `DEFAULT_LLM_TEMPERATURE=20` → an OpenAI 400 error on **every single LLM call**, discovered in production. `2.0` is the OpenAI API ceiling. |
| `MAX_LLM_CALL_RETRIES ge=0` | a negative retry count silently disabling retries — your resilience layer becomes a no-op and you don't find out until an outage |
| `JWT_ACCESS_TOKEN_EXPIRE_DAYS ge=1` | `0` or negative → every token is born expired, nobody can log in |
| `POSTGRES_PORT ge=1, le=65535` | catches `POSTGRES_PORT=54320` typos at startup instead of as a connection timeout 30 seconds later |

❓ **Why bother — isn't this over-careful?** Each of these is **one keyword argument** and each moves
a failure from "runtime, in production, with a confusing error" to "startup, with the field name and
the rule". That exchange rate is unbeatable. This is the cheapest defensive code in the entire
codebase.

🎯 **Agentic AI angle:** `TEMPERATURE` and `MAX_LLM_CALL_RETRIES` are agent-behaviour knobs. In an
agentic system these get tuned frequently, often by someone editing a `.env` in a hurry during an
incident. Constraints are the guardrail on that hurried edit.

---

## 13. Field validators — lines 169–179

```python
@field_validator("APP_ENV", mode="before")
@classmethod
def _normalise_app_env(cls, value: str) -> str:
    """Accept `Production`/` prod ` and friends without a separate alias table."""
    return value.strip().lower() if isinstance(value, str) else value


@field_validator("LOG_LEVEL", mode="before")
@classmethod
def _normalise_log_level(cls, value: str) -> str:
    """Uppercase so `LOG_LEVEL=debug` in a `.env` file works."""
    return value.strip().upper() if isinstance(value, str) else value
```

🍕 **Plain terms:** the receptionist tidying up the handwriting before filing the form. `" Production "`
becomes `"production"`. `"debug"` becomes `"DEBUG"`. Same meaning, one canonical shape.

🔧 **Technical:** `mode="before"` runs **before** pydantic's type coercion, on the raw input.

❓ **Why `mode="before"` and not `"after"`:** with `frozen=True` you cannot reassign a field after
construction, so an "after" validator has nothing to normalise *into*. Normalisation must happen on
the way in. (`mode="after"` is the right choice for *checking*, which is what
[§15](#15-_validate_startup_policy--lines-206254) does — it never mutates.)

❓ **Why the `isinstance(value, str)` guard:** a "before" validator receives whatever was passed —
including an `int` or `None` from a test or a bad source. `None.strip()` would raise `AttributeError`,
which pydantic reports as an internal error rather than a clean validation message. Passing non-strings
through untouched lets pydantic's normal type machinery produce the proper error.

❓ **Why `@classmethod`:** required by pydantic v2 — validators run before an instance exists.
Forgetting it is a common and confusing error.

❓ **What if we don't write these:**
- `APP_ENV=Production` → not in `ENVIRONMENT_TIERS` → app refuses to start with "Unknown APP_ENV:
  'Production'", which looks like a bug in *your* code to whoever is deploying at 6pm on a Friday.
- `LOG_LEVEL=debug` → `logging.setLevel("debug")` → `ValueError: Unknown level: 'debug'` from stdlib.

Both are "the config was morally correct and the app rejected it" — the most frustrating class of
error. Two lines each to eliminate.

> **The transferable idea:** **normalise at the boundary, validate after.** Every input from the
> outside world gets one canonical form before any logic touches it. Then all your comparisons are
> exact and you never write `.lower()` again anywhere downstream.

---

## 14. Properties — lines 181–204

Properties are **derived values** — things computed *from* settings rather than read from the
environment. Nothing here is configurable; each is a single source of truth for a transformation.

### `tier` — lines 181–184

```python
@property
def tier(self) -> DeploymentTier:
    """Policy class for `APP_ENV`. Validated at construction, so this never raises here."""
    return ENVIRONMENT_TIERS[self.APP_ENV]
```

🔧 **Technical:** a plain dict lookup with **no** `.get()` and **no** default. That's deliberate: the
model validator at line 213 already proved the key exists, so a `KeyError` here would be a genuine
programming bug, and it should crash loudly rather than return a lax default.

❓ **Why a property and not a stored field:** a field could be set independently of `APP_ENV` and
drift out of sync. A property is *always* consistent by construction. **Never store what you can
derive.**

🎯 **Where it fits:** this is what future layers branch on — `if settings.tier is
DeploymentTier.PRODUCTION:` to pick the real vector store vs. the in-memory one, the paid model vs.
the cheap one, real tools vs. mocked tools.

### `allowed_origins_list` — lines 186–189

```python
@property
def allowed_origins_list(self) -> list[str]:
    """CORS origins as a list."""
    return [origin.strip() for origin in self.ALLOWED_ORIGINS.split(",") if origin.strip()]
```

🍕 **Plain terms:** turns `"a, ,b "` into `["a", "b"]` — split on commas, trim spaces, drop empties.

❓ **Why the `if origin.strip()` filter:** `"a,,b".split(",")` gives `["a", "", "b"]`. An empty string
in the CORS allow-list is at best noise and at worst a matching quirk in a middleware. A trailing
comma in a `.env` file is extremely common. Verified by `test_allowed_origins_list_splits_and_strips`.

🎯 **Where it fits:** consumed by `main.py:38` → `CORSMiddleware(allow_origins=...)`, and read by the
production guard at line 246 to reject a wildcard.

### `postgres_dsn` — lines 191–204

```python
@property
def postgres_dsn(self) -> SecretStr:
    user = quote_plus(self.POSTGRES_USER)
    password = quote_plus(self.POSTGRES_PASSWORD.get_secret_value())
    return SecretStr(
        f"postgresql://{user}:{password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
    )
```

🍕 **Plain terms:** assembles the five separate database settings into the one connection string the
driver actually wants — and keeps it sealed, because it contains the password.

Three decisions in four lines:

**1. It returns `SecretStr`, not `str`.**

❓ **Why:** the DSN *contains the password*. If this returned a plain `str`, every protection from
[§12](#12-the-fields--lines-132167) would be undone the moment someone logged the DSN — which people
do constantly when debugging connection issues (`logger.info(f"connecting to {settings.postgres_dsn}")`).

❓ **Isn't `.get_secret_value()` at the call site annoying?** Slightly — and that's the point. It makes
every exposure a **visible, greppable, deliberate line of code**:

```python
engine = create_async_engine(settings.postgres_dsn.get_secret_value())
```

You can audit your whole codebase for credential exposure with one `grep`. That's worth 20 characters.

**2. `quote_plus` on user and password.**

Covered in [§3](#3-imports--lines-2739). Verified by
`test_postgres_dsn_is_secret_and_percent_encodes_credentials`, which asserts
`p@ss/word` → `p%40ss%2Fword`.

❓ **Why not on host/db/port too:** hostnames and database identifiers can't legally contain those
characters. Encoding them would be noise implying a risk that doesn't exist.

**3. It's a property, not a `DATABASE_URL` field.**

❓ **Why not just have one `DATABASE_URL` env var?** Because you'd lose the ability to override one
piece. In Docker Compose you want `POSTGRES_HOST=db`; locally `POSTGRES_HOST=localhost`; everything
else identical. With a monolithic URL, changing the host means rewriting the whole string in every
environment file — and every rewrite is a chance to fumble the password.

⚠️ **Known debt (already flagged in `pyproject.toml`):** the scheme is `postgresql://`, which
SQLAlchemy resolves to psycopg2. This project also has psycopg 3 (needed by
`langgraph-checkpoint-postgres`). Moving to `postgresql+psycopg://` lets you drop the
`psycopg2-binary` dependency entirely. One-line change here, deferred until there's actual DB code
to test it against.

---

## 15. `_validate_startup_policy` — lines 206–254

**This is the security heart of the file.** Everything above sets values; this decides whether the
process is *allowed to exist*.

```python
@model_validator(mode="after")
def _validate_startup_policy(self) -> Settings:
```

🍕 **Plain terms:** the final check at reception. All the forms are filled in and typed correctly —
now: *given who you claim to be, are these answers acceptable?* A visitor pass with no photo is fine
for the lobby and disqualifying for the server room.

🔧 **Technical:** `mode="after"` runs **once**, after every field has been parsed and type-checked,
with a fully-built `self`. That's required here because the rules are **cross-field**: "DEBUG must be
false" only matters *given* what `APP_ENV` is. A per-field validator can't see other fields.

❓ **Why one validator instead of five small ones:** the rules aren't independent — they're a single
policy that reads top-to-bottom as a coherent story ("what's always wrong" → "am I strict?" → "what's
wrong for strict tiers" → "what's wrong for production"). Splitting it would scatter one decision
across five places and lose the ordering.

### Layer 1: rules that apply everywhere — lines 213–227

```python
tier = ENVIRONMENT_TIERS.get(self.APP_ENV)
if tier is None:
    raise ConfigurationError(
        f"Unknown APP_ENV: {self.APP_ENV!r}",
        known_environments=sorted(ENVIRONMENT_TIERS),
        hint="add it to ENVIRONMENT_TIERS with the policy tier it belongs to",
    )
```

❓ **Note `.get()` here but `[]` in the `tier` property:** intentional. *This* is the place that
handles a missing key — it's the validation boundary. The property runs afterwards and can assume
success. One place owns the check.

❓ **Why the error carries `known_environments` and `hint`:** because the person reading this message
is deploying, possibly at night, possibly not the person who wrote the code. `AppException.log_context()`
turns those kwargs into structured log fields, so they get:

```
Unknown APP_ENV: 'prodction'
  known_environments: ['ci','dev','development','local','preprod','prod','production','qa','sit','stage','staging','test','uat']
  hint: add it to ENVIRONMENT_TIERS with the policy tier it belongs to
```

They fix it in ten seconds. Compare to `KeyError: 'prodction'`.

> **The transferable idea:** an error message should contain **what was wrong, what's valid, and what
> to do**. Most error messages contain only the first.

```python
if self.LOG_LEVEL not in logging.getLevelNamesMapping():
    raise ConfigurationError(f"Unknown LOG_LEVEL: {self.LOG_LEVEL!r}", valid_levels=sorted(...))
```

Covered in [§3](#3-imports--lines-2739). Note this applies on **every** tier — a broken log level in
development is still broken.

### The early exit — lines 229–230

```python
if tier not in _STRICT_TIERS:
    return self
```

🍕 **Plain terms:** "you're in the lobby, not the server room — off you go."

🔧 **Technical:** a guard clause. Everything below is strict-tier-only, and this one line means the
rest of the function doesn't need to be indented inside an `if`, and doesn't need to re-check the
tier at each step.

❓ **Why does DEVELOPMENT get a pass at all?** Because `.env.example` **must boot out of the box**. If
`git clone && cp .env.example .env && uv run uvicorn app.main:app` fails with "JWT_SECRET_KEY is a
placeholder", every new developer's first experience is a config error. Strictness where it matters,
leniency where it doesn't — that's what the tier system buys you.

### Layer 2: strict-tier rules — lines 232–243

```python
if self.DEBUG:
    raise ConfigurationError("DEBUG must be false outside development", app_env=..., tier=...)
```

❓ **What if we don't:** FastAPI's `debug=True` returns full stack traces to the client on unhandled
errors — file paths, local variable values, library versions, and frequently fragments of secrets.
It's an information-disclosure vulnerability, and it's one of the most common findings in real
production audits precisely because it's a single flag nobody re-checked.

```python
for name, secret in (
    ("JWT_SECRET_KEY", self.JWT_SECRET_KEY),
    ("OPENAI_API_KEY", self.OPENAI_API_KEY),
    ("POSTGRES_PASSWORD", self.POSTGRES_PASSWORD),
):
    if _is_placeholder(secret):
        raise ConfigurationError(f"{name} is unset or still a placeholder", ...)
```

🍕 **Plain terms:** "you can't work in the server room with a photocopied badge."

❓ **Why a loop over a tuple of pairs, instead of three `if` statements:** three ifs would be nine
lines of near-identical code, and adding a fourth secret means copy-pasting a block (and getting the
name string wrong in the copy). The loop makes adding `ANTHROPIC_API_KEY` a **one-line** change.
Parameterised the same way in the test — `@pytest.mark.parametrize("field", sorted(PROD_SECRETS))` —
so all three are covered by one test body.

❓ **Why is `LANGFUSE_SECRET_KEY` not in this list:** because observability being unconfigured
degrades your visibility but doesn't compromise correctness or security. Refusing to start production
because tracing isn't set up would be the guard doing more harm than good. **A guard that fires on
non-critical things gets disabled.**

⚠️ **Note the error message says only the field name — never the value.** `f"{name} is unset..."`,
not `f"{name} is {secret}"`. An error message is a log line; a log line is forever.

### Layer 3: production-only rules — lines 245–252

```python
if tier is DeploymentTier.PRODUCTION:
    if "*" in self.allowed_origins_list:
        raise ConfigurationError("ALLOWED_ORIGINS must not be a wildcard in production")
    if len(self.JWT_SECRET_KEY.get_secret_value()) < _MIN_PRODUCTION_SECRET_LENGTH:
        raise ConfigurationError("JWT_SECRET_KEY is too short for production", minimum_length=...)
```

**Wildcard CORS.** `allow_origins=["*"]` combined with `allow_credentials=True` (which
[`main.py:39`](../app/main.py) sets) means **any website on the internet** can make authenticated
requests to your API using a logged-in user's cookies. That's a textbook CSRF exposure. Browsers
actually reject that exact combination, which means the practical result is your real frontend
breaking in production while the config *looks* permissive. Both outcomes are bad; neither is
detectable without this check.

❓ **Why is wildcard CORS allowed on staging:** staging often has ephemeral preview URLs
(`pr-142.preview.vercel.app`) that can't be enumerated in advance. Tolerable there, never in
production. Verified by `test_staging_allows_short_jwt_secret_and_wildcard`.

**Secret length.** Covered in [§7](#7-the-three-module-constants--lines-7784).

❓ **Why is this production-only:** staging secrets are frequently rotated dev-generated values.
Blocking a staging deploy over key length is friction with no matching risk — staging holds no
customer data.

### `return self` — line 254

Required by the `mode="after"` contract: the validator must return the model (it may return a
modified copy). Returning `self` unchanged is the "I only checked, I didn't touch anything" signal.

---

## 16. `get_settings()` — lines 257–265

```python
@lru_cache
def get_settings() -> Settings:
    """Return the process-wide `Settings`, reading the environment exactly once. ..."""
    return Settings()
```

🍕 **Plain terms:** read the register once at 9am, then hand out the **same copy** to everyone who
asks. Don't re-read the filing cabinet on every request.

🔧 **Technical:** `functools.lru_cache` on a zero-argument function is a memoised singleton. First
call constructs `Settings` (reads files, parses, validates, runs the guard). Every later call returns
the identical object.

### ❓ Why cache at all?

Without it, every `get_settings()` would:
1. open and parse up to four `.env` files from disk
2. re-read the whole process environment
3. re-validate ~20 fields
4. re-run the startup guard

In a FastAPI app that could be **per request**, on the hot path, doing **file I/O in an async event
loop** — which blocks the loop, because `open()` isn't awaitable. Under load that's a real latency
regression from an unexpected place.

### ❓ Why `@lru_cache` and not `settings = Settings()` at module level?

This is the second-most-important decision in the file. The article did it the module-level way, and
so did the previous version here. The difference:

| | Module-level `settings = Settings()` | `@lru_cache def get_settings()` |
|---|---|---|
| When does env get read? | **At import** — the instant anything imports this module | On **first call** — you control when |
| Can a test choose the environment? | ❌ Import already happened. Needs `importlib.reload` hacks. | ✅ `monkeypatch.setenv(...)` then `cache_clear()` |
| Does importing the module have side effects? | ❌ Yes — reads disk, may raise | ✅ No. Import is inert. |
| Works with FastAPI `Depends`? | Awkwardly | ✅ Natively: `Depends(get_settings)` |
| Can you override it in tests? | ❌ | ✅ `app.dependency_overrides[get_settings] = fake` |

The last row is the one that pays off later. When you build the API layer, an endpoint written as
`def chat(settings: Settings = Depends(get_settings))` can be tested against a fake config **without
touching the environment at all**. That's the Dependency Inversion Principle made concrete: the
endpoint depends on the *ability to get settings*, not on a specific global object.

### ❓ Why is `cache_clear()` important?

It's the **test seam**. `lru_cache` gives it to you free:

```python
def test_something(monkeypatch):
    get_settings.cache_clear()              # forget the old one
    monkeypatch.setenv("APP_ENV", "test")   # choose the environment
    settings = get_settings()               # built fresh
```

Verified by `test_get_settings_is_cached_and_clearable`, which asserts both that repeated calls return
the *identical* object and that `cache_clear()` produces a different one.

### ❓ Is `lru_cache` thread-safe?

Yes for the cache itself. There's a narrow race where two threads calling simultaneously on a cold
cache could both construct a `Settings` — harmless here, since construction is pure and the objects
are frozen and equal. And in practice `create_app()` warms it during startup, before any concurrency.

> **The transferable idea:** **a module import should never have side effects.** No file reads, no
> network, no `print`, no raising. Put the work behind a function and cache the function. The article's
> version printed to stdout and read the disk at import time — which is why it was untestable.

---

## 17. SOLID scorecard

You asked for SOLID specifically. Here's an honest mapping — including where it's deliberately *not*
applied, because cargo-culting SOLID produces worse code than ignoring it.

| Principle | How this file honours it |
|---|---|
| **S** — Single Responsibility | `Settings` only *holds and validates* config. It doesn't load `.env` (that's `_env_files`), doesn't judge secrets (`_is_placeholder`), doesn't detect the environment (`_current_app_env`), doesn't own the logging registry (`logging.py` does). Contrast the article's `__init__`, which did all five. |
| **O** — Open/Closed | New environment = one row in `ENVIRONMENT_TIERS` + one `.env` file. New secret in the guard = one line in the loop tuple. New config source (Key Vault) = override `settings_customise_sources`. **The guard's branches never change.** |
| **L** — Liskov Substitution | Any object with `LOG_LEVEL: str` and `LOG_FORMAT: str` can be passed to `configure_logging` — a real `Settings`, a test stub, a future `RemoteSettings`. No call site can tell the difference. |
| **I** — Interface Segregation | `logging.py` depends on a **5-field** `LoggingConfig` Protocol, not on the 20-field `Settings`. It can be configured and tested without loading a single `.env` file. Every future module does the same: declare the narrow slice you need. |
| **D** — Dependency Inversion | Consumers depend on `get_settings` (a callable) and on Protocols (abstractions), not on a module-level global (a concretion). FastAPI's `Depends(get_settings)` makes that swappable per-test. |

### ⚠️ Where SOLID is deliberately NOT applied

There is **no** `ConfigProvider` ABC with a single `EnvConfigProvider` implementation. That's the
classic over-engineering trap and it would be strictly worse:

- an interface with one implementation is indirection with no substitution
- Python's structural typing (`Protocol`) already gives you substitutability **without** an inheritance hierarchy
- pydantic-settings' `settings_customise_sources` is the *real* extension point for new config
  sources, and it lives on `BaseSettings` — a hand-rolled ABC would sit *beside* it, giving you two
  competing extension mechanisms

> **The transferable idea:** SOLID is about **where the seams go**, not about how many abstract
> classes you own. This file has exactly three seams — the tier table, the Protocol boundary, and
> the cached factory — and each one exists because something concrete will plug into it.

---

## 18. Where this fits in the 7 layers

```
                    ┌─────────────────────────────────┐
                    │  app/core/config.py  (Layer 0)  │
                    │  the only door to the outside   │
                    └───────────────┬─────────────────┘
                                    │ get_settings()
      ┌──────────────┬──────────────┼──────────────┬──────────────┐
      ▼              ▼              ▼              ▼              ▼
 ┌─────────┐  ┌────────────┐  ┌──────────┐  ┌──────────┐  ┌────────────┐
 │ Logging │  │  Database  │  │   LLM    │  │   Auth   │  │Observability│
 │ L7 obs. │  │ L1 persist │  │ L3 reason│  │ L2 gate  │  │  L7 traces  │
 ├─────────┤  ├────────────┤  ├──────────┤  ├──────────┤  ├────────────┤
 │LOG_LEVEL│  │postgres_dsn│  │OPENAI_KEY│  │JWT_SECRET│  │LANGFUSE_*  │
 │LOG_FORMAT│ │POSTGRES_*  │  │MODEL/TEMP│  │JWT_ALGO  │  │LANGFUSE_HOST│
 │ ✅ wired │  │ ⏳ pending │  │⏳ pending│  │⏳ pending│  │ ⏳ pending  │
 └─────────┘  └────────────┘  └──────────┘  └──────────┘  └────────────┘
```

**Why Layer 0 and not one of the seven:** every layer needs config, so config can't be *inside* any
of them without creating a circular dependency. It sits underneath, next to `exceptions.py` — the
two modules with (almost) no dependencies of their own.

**Why config is uniquely load-bearing in an agentic system:**

| Ordinary web app | Agentic AI system |
|---|---|
| A wrong DB password → immediate, obvious crash | A wrong `TEMPERATURE` → the agent gets subtly worse and **nothing errors** |
| Secrets leak via logs | Secrets leak via logs **and via LLM traces sent to a third-party SaaS** |
| One external dependency (the DB) | Five or more paid APIs, each with its own key, rate limit, and cost |
| Config drift costs correctness | Config drift costs correctness **and money, per token, per request** |

An agent misconfigured against the wrong model or the wrong temperature doesn't fail — it *degrades*.
There's no exception to catch. Startup validation is the only place you can catch it at all.

---

## 19. How to extend it

### Add a new environment (e.g. `perf`)

```python
# 1. one row in ENVIRONMENT_TIERS
"perf": DeploymentTier.STAGING,
```
```bash
# 2. one file
cp .env.example .env.perf     # already gitignored by `.env.*`
# 3. deploy with APP_ENV=perf
```
No other code changes. That's the OCP payoff.

### Add a new setting

```python
ANTHROPIC_API_KEY: SecretStr = SecretStr("")     # secret → SecretStr
MAX_AGENT_STEPS: int = Field(default=10, ge=1)   # numeric → constrain it
```
Then add it to `.env.example` with a `your-` placeholder — the guard picks it up automatically once
you add it to the loop at line 235.

### Add a cloud secret store (Key Vault / Secrets Manager / SSM)

Nothing here needs redesigning. `BaseSettings` has a built-in hook:

```python
@classmethod
def settings_customise_sources(cls, settings_cls, init_settings, env_settings,
                               dotenv_settings, file_secret_settings):
    return (init_settings, KeyVaultSource(settings_cls), env_settings, dotenv_settings)
    #                       ↑ insert wherever you want it in the precedence order
```

The tuple **is** the precedence order (first = highest). You write one `PydanticBaseSettingsSource`
subclass with a `__call__` returning a dict, and every field, validator, guard, and test below it
keeps working untouched.

❓ **Why isn't this stubbed out already?** Because a no-op override is scaffolding for a decision
nobody has made yet — which vault, which auth mode, which fields come from it. The hook exists in the
library whether or not we mention it; writing an empty version today would just be a file to delete
later. Documented, not built.

### Flip `extra` to `"forbid"`

Once every key in `.env.example` has a field (i.e. once rate limiting is wired), change
`extra="ignore"` → `extra="forbid"` at line 127. Typo'd env vars then fail at startup instead of
silently using defaults.

---

## 20. Cheat sheet

```
PRECEDENCE (lowest → highest)
  field default → .env → .env.local → .env.<env> → .env.<env>.local → real env vars → kwargs

TWO CONCEPTS, NEVER CONFLATE
  APP_ENV        free-form room name  → picks the .env file       ("uat", "sit", "perf")
  DeploymentTier policy clearance     → picks the rules            (4 fixed values)

THE GUARD, IN ORDER
  always      unknown APP_ENV      → raise
  always      unknown LOG_LEVEL    → raise
  strict      DEBUG=true           → raise      (staging + production)
  strict      placeholder secret   → raise
  production  wildcard CORS        → raise
  production  JWT secret < 32      → raise

SECRETS
  declare     OPENAI_API_KEY: SecretStr = SecretStr("")
  read        settings.OPENAI_API_KEY.get_secret_value()      ← greppable by design
  never       logger.info(settings.SOMETHING.get_secret_value())

USE IT
  app code    settings = get_settings()
  FastAPI     def route(cfg: Settings = Depends(get_settings)): ...
  tests       get_settings.cache_clear(); monkeypatch.setenv(...); get_settings()
  isolation   Settings(_env_file=None, APP_ENV="production", ...)

NEVER
  ✗ from app.core.config import settings        (module-level singleton — deleted on purpose)
  ✗ settings.DEBUG = True                       (frozen — raises ValidationError)
  ✗ a hardcoded list of valid log levels        (ask stdlib)
  ✗ case _: return DEVELOPMENT                  (fails open — the worst default in config)
```

### Verification commands

```bash
uv run pytest tests/test_config.py -v      # 20 tests, config.py at 100% coverage
uv run ruff check app tests
uv run mypy app
uv run python -c "from app.main import create_app; create_app(); print('boots')"
```

---

## 📎 Related files

| File | Relationship |
|---|---|
| [`.env.example`](../.env.example) | the keys this file expects — see [`1_env_guide.md`](./1_env_guide.md) |
| [`app/core/exceptions.py`](../app/core/exceptions.py) | `ConfigurationError`, raised by the guard |
| [`app/core/logging.py`](../app/core/logging.py) | consumes 5 fields via the `LoggingConfig` Protocol — see [`4_logging_guide.md`](./4_logging_guide.md) |
| [`app/main.py`](../app/main.py) | calls `get_settings()` inside `create_app()` |
| [`tests/test_config.py`](../tests/test_config.py) | every claim in this guide is asserted there |
| [`pyproject.toml`](../pyproject.toml) | see [`2_pyproject_toml_guide.md`](./2_pyproject_toml_guide.md) |

---

*Last updated: 2026-08-16 | Based on `app/core/config.py` of the `production_agentic_ai` project*
