# 🔌 How the core layer wires together — from `.env.example` to a running app

> **Purpose:** The other five guides explain each file *on its own*. This one explains how they
> **connect** — the path a single setting travels from a text file on disk to the moment the app
> either starts serving or refuses to. Written in plain English first, with the real code alongside.
>
> **Written:** 2026-09-06, while closing the last open half of the Appendix C deviation dated
> 2026-07-25 (*"logging can't be bolted on after the foundation, it has to wrap the foundation"*).
> That fix is documented in [§9](#9-the-chicken-and-egg-problem-and-how-it-was-fixed) and in
> [`decisions/0001-bootstrap-error-reporting.md`](../decisions/0001-bootstrap-error-reporting.md).
>
> **Companion docs:** [`1_env_guide.md`](./1_env_guide.md) (what each variable means) ·
> [`3_config_py_guide.md`](./3_config_py_guide.md) (how settings load) ·
> [`4_logging_guide.md`](./4_logging_guide.md) (how log lines are made) ·
> [`5_exception_handling_guide.md`](./5_exception_handling_guide.md) (how failures are shaped).
> This guide assumes none of them and links back where it matters.

---

## The big picture: two kinds of breakage

Your app can break in exactly two ways, and they need opposite treatments.

| | **Break #1 — never set up right** | **Break #2 — goes wrong while running** |
|---|---|---|
| Example | wrong database address, missing API key, "anyone may connect" left on | provider outage, weird user input, cost spiral |
| Shop analogy | you opened the doors having forgotten to lock the safe | a supplier failed to deliver at lunchtime |
| Avoidable? | **Completely** | No |
| Treatment | **refuse to open** | alarms, retries, fallbacks |

Break #2 is what most of the Bible is about. **This layer is entirely about Break #1** — and about
one specific danger: an unset-up app doesn't *look* broken. It starts fine. It serves requests. It
just serves them against the wrong database, or signs login tokens with a password that is public in
your git history. Then, months later, it looks exactly like a Break #2 and you lose a night to it.

So the whole core layer enforces one rule:

> **If the shop isn't set up correctly, refuse to open the doors. Don't open and hope.**

Everything below is a mechanism for that rule.

---

## The journey of one setting

```
.env.example          the blank form pinned in the back office
      │
      ▼  (you copy and fill it in)
.env / .env.production  the filled-in form for THIS environment
      │
      ▼  (config.py reads it, in a fixed order of precedence)
Settings              typed, checked, laminated — or the app dies here
      │
      ├──▶ logging.py            takes 5 facts   ("how should I format lines?")
      ├──▶ exception_handlers.py takes 1 fact    ("is debug mode on?")
      └──▶ main.py               takes the rest  (title, CORS, version)
```

Nine stages follow, in that order.

---

## 1. `.env.example` is a blank form, and the blanks are bait

```bash
# .env.example
JWT_SECRET_KEY="your-jwt-secret-key"
POSTGRES_PASSWORD=mypassword
```

**Plain English.** This is the blank checklist pinned in the back office. Nobody opens the shop with
*this* copy — you photocopy it, fill it in for your specific shop, and use that.

Two non-obvious jobs:

**It is the documentation.** Every line matches a setting the app expects. When someone adds a
setting in code and forgets it here, the next person copies an incomplete form and finds out the
painful way.

**The fake values are deliberate bait.** `"your-jwt-secret-key"` and `mypassword` are not lazy
filler — `config.py` actively hunts for them:

```python
_PLACEHOLDER_SECRETS = frozenset({"change-me", "changeme", "secret", "password", "mypassword", "postgres"})

def _is_placeholder(secret: SecretStr) -> bool:
    """True when a secret is empty or still holds an example/scaffold value."""
    value = secret.get_secret_value().strip().lower()
    return not value or value in _PLACEHOLDER_SECRETS or value.startswith("your-")
```

In plain words: *"Is this still empty, still one of the obvious fake passwords, or does it still
start with `your-`? Then nobody filled it in."*

The `your-` prefix is the clever half. Because **every** fake value in the example file starts with
it, the check covers all of them without listing them one by one — and any secret added to
`.env.example` tomorrow gets the same protection for free.

> **What breaks if you skip it.** Someone copies the form, fills in three of five blanks, deploys to
> real customers, and the app boots **perfectly** on a publicly-known password. Nothing looks wrong.
> That is what makes it dangerous.

---

## 2. The app must know *which* shop before it can read that shop's notes

```python
def _current_app_env() -> str:
    """Read `APP_ENV` from the *process* environment."""
    return os.getenv("APP_ENV", "development").strip().lower()
```

**Plain English.** `APP_ENV` answers *"which environment am I? My laptop? A test server? Real
customers?"* — and that answer decides **which file to read**. So the answer cannot live inside one
of those files.

> You can't find a building's address by reading a note that's inside the building.

That's why this reads the **process environment** directly (`os.getenv`), not a file. Practical
consequence: `APP_ENV` is always handed in from outside — Docker `-e`, Compose `environment:`, Azure
Container Apps config — never from a `.env` file. Writing `APP_ENV=production` inside
`.env.production` does nothing at all, because that file was never selected.

---

## 3. Layers of instructions, most specific wins

```python
def _env_files(app_env: str) -> tuple[Path, ...]:
    """Env files in ascending precedence — later entries win, absent entries are skipped."""
    return (
        PROJECT_ROOT / ".env",                       # rules for everyone
        PROJECT_ROOT / ".env.local",                 # your machine only (gitignored)
        PROJECT_ROOT / f".env.{app_env}",            # what this deployment provides
        PROJECT_ROOT / f".env.{app_env}.local",      # your override of that
    )
    # ...and real process environment variables beat all four.
```

**Plain English.** Company policy → office policy → team policy → the sticky note on your desk. The
sticky note wins. A missing layer is simply skipped.

Two quiet decisions worth stealing:

**Files are found by "where am I installed?", not "where was I launched from."**

```python
PROJECT_ROOT = Path(__file__).resolve().parents[2]
```

This sounds pedantic. It isn't. Without it, the app finds settings when started from the repo root
and silently finds **none** when started from elsewhere — including in CI. Nothing crashes; the
settings just come out empty. That bug costs an afternoon the first time you meet it.

**Missing files are fine, not an error.** A real production container usually ships **zero** of these
files and has every setting injected directly. If missing files raised, you'd have to create empty
ones to keep the app happy. Here, "no files at all" is a valid configuration.

---

## 4. Everything arrives as text, so something has to check it

```python
POSTGRES_PORT: int = Field(default=5432, ge=1, le=65535)
DEFAULT_LLM_TEMPERATURE: float = Field(default=0.0, ge=0.0, le=2.0)
JWT_SECRET_KEY: SecretStr = SecretStr("change-me")
```

**Plain English.** Every setting arrives as **text**. Always. The number `5432` arrives as the
characters `"5432"` — the same way a handwritten form is just ink, and the box labelled "age"
doesn't magically contain a number.

So checking happens here, once, at the door: *is this really a number? Is the port in range 1–65535?
Is the AI's creativity setting between 0 and 2?* Do it here — or find out deep inside the app, at the
worst possible moment.

### `SecretStr`: the sealed envelope

It is **not encryption**. It's writing the password on a card and sealing it in an envelope.

You can carry the envelope around, store it, pass it to functions. But anyone who photocopies it —
which is what logging does — gets a black rectangle, not the password. To actually **read** it you
must deliberately tear it open:

```python
password = self.POSTGRES_PASSWORD.get_secret_value()   # visible, greppable, reviewable
```

That converts leaking a secret from *something that happens by accident at 2am* into *something you
did on purpose, on a line a reviewer can see*.

Watch how far the envelope is carried:

```python
@property
def postgres_dsn(self) -> SecretStr:
    """SQLAlchemy/psycopg connection string."""
    user = quote_plus(self.POSTGRES_USER)
    password = quote_plus(self.POSTGRES_PASSWORD.get_secret_value())
    return SecretStr(f"postgresql://{user}:{password}@{self.POSTGRES_HOST}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}")
```

This builds the database address, which has the **password baked into the middle of it** — so it
stays sealed. A weaker design returns plain text here and undoes the protection at the exact point
it matters most: connection strings are the most commonly leaked credential there is.

*(`quote_plus` is the small correctness win — a password containing `@` or `/` would otherwise
silently produce a malformed URL.)*

---

## 5. A shop's **name** and a shop's **type** are different things

This is the idea most worth carrying to other projects.

```python
ENVIRONMENT_TIERS: dict[str, DeploymentTier] = {
    "sit":      DeploymentTier.STAGING,
    "uat":      DeploymentTier.STAGING,
    "preprod":  DeploymentTier.STAGING,
    "prod":     DeploymentTier.PRODUCTION,
    "production": DeploymentTier.PRODUCTION,
    # ...
}
```

**Plain English.**

- Branch **names** — Oxford Street, Camden, Soho, Leeds. Names multiply; you'll have ten.
- Branch **types** — flagship, pop-up, warehouse. Types don't multiply; there are four, forever.

**Rules are written against the type, never the list of names.**

Get it wrong and your safety check becomes *"if the branch is Oxford Street or Camden or Soho or
Leeds, lock the safe"* — a list someone must extend **in every place a rule is checked**, every time
infra adds an environment. Eventually somebody adds "Leeds 2", misses one list, and that branch runs
all year with the safe unlocked.

Get it right and **adding an environment is one row of data, and no safety rule changes.**

A second protection sits alongside it — unknown names are *rejected*, never defaulted:

```python
tier = ENVIRONMENT_TIERS.get(self.APP_ENV)
if tier is None:
    raise ConfigurationError(
        f"Unknown APP_ENV: {self.APP_ENV!r}",
        known_environments=sorted(ENVIRONMENT_TIERS),
        hint="add it to ENVIRONMENT_TIERS with the policy tier it belongs to",
    )
```

Typo `prd` instead of `prod` and the app **refuses to start**. It does not shrug and assume "must be
a dev machine then" — that shrug is exactly how a customer-facing server ends up with every
developer safety rail switched off.

---

## 6. The pre-flight check — the actual point of the whole file

Think of a pilot's checklist: if an item fails, the plane **does not take off**.

```python
@model_validator(mode="after")
def _validate_startup_policy(self) -> Settings:
```

It runs in three widening circles.

| Circle | Applies to | Checks |
|---|---|---|
| **1 — always** | every environment | real `APP_ENV`? real `LOG_LEVEL`? |
| **2 — shared servers** | staging + production | `DEBUG` off; no placeholder secrets |
| **3 — real customers** | production only | no wildcard CORS; `JWT_SECRET_KEY` ≥ 32 chars |

Why this is the big win: **each of those is a genuine security hole.**

| Left unchecked | What an attacker gets |
|---|---|
| `DEBUG=true` in production | your error responses hand back internal details — file paths, raw values, internals — to anyone who triggers an error on purpose |
| Wildcard CORS | any website on the internet can make requests as your logged-in users |
| Short JWT secret | brute-forceable, then anyone can forge a login |

All three would otherwise be found by an auditor, or by an attacker, months later. This file converts
them into **one loud crash at startup, in front of the person deploying, while they're still looking
at the screen.** That is the trade the whole file exists to make.

> **Small detail worth stealing.** The log-level check asks Python's own registry rather than a
> hand-written list:
> ```python
> if self.LOG_LEVEL not in logging.getLevelNamesMapping():
> ```
> The list can never go stale, and a custom level added later is accepted automatically. Whenever you
> can *ask* the source of truth instead of copying it, do.

---

## 7. Laminated, and read once

```python
model_config = SettingsConfigDict(..., frozen=True)

@lru_cache
def get_settings() -> Settings:
    return Settings()
```

**`frozen=True` — the rules are printed and laminated.** Nobody can scribble on them mid-shift. This
matters more than it sounds: the app serves many customers *at the same time*. If one request could
change a setting "just temporarily", another request happening simultaneously silently gets the
changed version. That bug appears at random, can't be reproduced, and takes days to find.

**`@lru_cache` — read once, remember the answer.** The subtle one. Compare:

| | Read on import (`settings = Settings()` at module level) | Read on first call (`@lru_cache`) |
|---|---|---|
| Production | identical | identical |
| A test wanting to pretend it's production | **impossible** — already read, probably during an unrelated import | `monkeypatch.setenv(...)` then `get_settings.cache_clear()` |

Real usage is the same either way. But the cached version means you can **rehearse** — which is the
only reason `tests/test_config.py` can exercise the production safety rules without a production
server.

---

## 8. The punchline — config is a supplier, not a town square

Here is who actually imports whom, measured from the code:

```
error_context.py       ──▶ (stdlib only)
exceptions.py          ──▶ error_context
log_sanitizer.py       ──▶ (pydantic only)
config.py              ──▶ exceptions
logging.py             ──▶ exceptions, log_sanitizer
middleware.py          ──▶ logging
exception_handlers.py  ──▶ error_context, exceptions, log_sanitizer, logging
main.py                ──▶ config, exception_handlers, exceptions, logging, middleware
```

**Exactly one production file imports `config.py`: `main.py`.**

That is backwards from most projects, where settings become a **town square** and every file walks
over to help itself. Here settings are a **supplier that only the manager visits**.

So how does logging get settings if it never asks for them? It writes a **job description** instead:

```python
@runtime_checkable
class LoggingConfig(Protocol):
    """The only settings this module needs."""
    LOG_LEVEL: str
    LOG_FORMAT: str
    PROJECT_NAME: str
    VERSION: str
    APP_ENV: str
```

In plain words: *"To do my job I need exactly these five facts. I don't care who you are. If you can
supply them, we're done."* The error handlers write a shorter one:

```python
class ErrorDetailConfig(Protocol):
    """The only setting these handlers need."""
    DEBUG: bool
```

`Settings` happens to have all of those, so it qualifies for both jobs — **without being told about
either.** No registration, no inheritance, no base class. It just fits. Four things fall out:

1. **No circular tangles.** `config.py` needs the error types, so it imports `exceptions`. If
   `logging.py` reached back for `config.py`, you'd get a loop (A needs B needs A) — a genuinely
   nasty class of bug. Job descriptions keep every arrow pointing one way.
2. **Honest labelling.** `configure_logging(config: LoggingConfig)` says at a glance it reads five
   settings. `configure_logging(settings: Settings)` says nothing — it could read any of the twenty.
3. **Simpler tests.** To test logging you hand it a five-field fake. You do not need a database
   password to test log formatting.
4. **Visible blast radius.** Rename a setting and the type checker points at every job description
   that wanted it. Delete one nobody asked for and nothing breaks — because nobody was using it.

And `main.py`, where it converges, stays deliberately boring:

```python
settings = get_settings()                    # read the checklist, or refuse to open
configure_logging(settings)                  # hand it to logging (5 facts)
app = FastAPI(title=settings.PROJECT_NAME, version=settings.VERSION, debug=settings.DEBUG)
app.add_middleware(RequestContextMiddleware)                          # give every request an ID
app.add_middleware(CORSMiddleware, allow_origins=settings.allowed_origins_list)
for exception_type, handler in build_exception_handlers(settings).items():   # (1 fact)
    app.add_exception_handler(exception_type, handler)
```

One checklist, read once, handed to two consumers that each see only their own slice. **When the
wiring is this boring, the design underneath is doing its job.**

---

## 9. The chicken-and-egg problem, and how it was fixed

### The symptom

Typo the environment name and, until 2026-09-06, this is all you got:

```
$ APP_ENV=prd python -c "import app.main"

app.core.exceptions.ConfigurationError: Unknown APP_ENV: 'prd'
```

You are told you are wrong. You are **not** told what right looks like — even though the app is
holding the answer. Look again at §5: that exception was constructed with
`known_environments=sorted(ENVIRONMENT_TIERS)` and a `hint`. Both were built, attached, and thrown
away.

> It's a smoke alarm that knows which room the smoke is in, and only beeps.

### Why it happened (genuinely awkward, not sloppy)

```python
settings = get_settings()      # ← the error happens HERE
configure_logging(settings)    # ← the thing that would print it nicely starts HERE
```

Settings must be read **before** logging can be configured, because logging is configured *from*
settings (`LOG_LEVEL`, `LOG_FORMAT`). So there is one window at process start with **no log pipeline
at all** — and the single failure family guaranteed to land in it is the `ConfigurationError` that
reading settings raises. Chicken, meet egg.

Python's default traceback prints `str(exc)`, which is only `message`. The three carefully separated
audiences on `AppException` — `log_context()`, `client_payload()`, `debug_payload()` — are all
unused here, because nothing is configured to call them.

### The fix

A small reporter in `logging.py`, because *"how this process emits a line"* is that module's job —
including the case where its own pipeline doesn't exist yet:

```python
def report_bootstrap_error(exc: AppException) -> None:
    """Write a startup failure to stderr, for the window *before* `configure_logging()` has run."""
    context = sanitise(exc.log_context())
    lines = [
        "",
        "=" * 72,
        "STARTUP FAILED -- the application did not begin serving.",
        "=" * 72,
        f"  {exc.error_code}: {exc.message}",
    ]
    lines.extend(f"  {key}: {value}" for key, value in context.items() if key not in _BOOTSTRAP_HEADLINE_KEYS)
    lines.append("")
    print("\n".join(lines), file=sys.stderr, flush=True)
```

Called from one `try/except` in `main.py`:

```python
try:
    settings = get_settings()
except AppException as exc:
    report_bootstrap_error(exc)
    raise
```

Three details that are the whole design:

| Detail | Why |
|---|---|
| `raise` at the end | **Reporting must never become swallowing.** A misconfigured process still has to die. `tests/test_logging.py` asserts the exception propagates, not merely that output appeared. |
| `sanitise(...)` | stderr in a container is scraped by the same aggregator as stdout — it's a **third sink**. `log_sanitizer.py` states the rule: *"A leak-prevention rule that only guards one sink is a rule with a hole in it."* |
| Plain text, not JSON | The only reader of this output is a human watching a container fail to start. |

### The result

```
========================================================================
STARTUP FAILED -- the application did not begin serving.
========================================================================
  configuration_error: Unknown APP_ENV: 'prd'
  error_id: f2a5ab3c4199
  known_environments: ['ci', 'dev', 'development', 'local', 'preprod', 'prod', 'production', 'qa', 'sit', 'stage', 'staging', 'test', 'uat']
  hint: add it to ENVIRONMENT_TIERS with the policy tier it belongs to
  raised_at: app/core/config.py:215 in Settings._validate_startup_policy
  raised_in_module: app.core.config

Traceback (most recent call last):
  ...
```

You get the valid list, the instruction, and the exact line that rejected you — and the process still
dies, traceback intact.

### Why the catch works at all — one constraint worth knowing

`get_settings()` contains no `raise` and no `try`, so at first glance nothing in it can fail:

```python
@lru_cache
def get_settings() -> Settings:
    return Settings()          # ← the raise happens in here
```

Constructing `Settings()` runs pydantic's validation, which runs `_validate_startup_policy`, which
raises. The exception then travels **up** through pydantic and out of `get_settings()`, because
nothing in between catches it — ordinary Python. The real chain:

```
config.py:215  _validate_startup_policy()   ← raise ConfigurationError
pydantic       BaseSettings.__init__()      ← passes through
pydantic       BaseModel.__init__()         ← passes through
config.py:265  get_settings()               ← passes through
main.py        create_app()                 ← except AppException  ✅
```

**But pydantic does not always pass through.** Think of it as a mail room your error travels through:

> *"If the parcel arrives in one of my standard envelopes, I open it and repack the contents into my
> own official complaint box. Any other parcel, I forward untouched."*

Its "standard envelopes" are exactly two error types — **`ValueError`** and **`AssertionError`** — and
its complaint box is **`ValidationError`**.

| Validator raises | What the caller actually receives | `except AppException` matches? |
|---|---|---|
| `ValueError` / `AssertionError` | `ValidationError` (repacked) | ❌ no |
| anything else | the original exception | ✅ yes |

`AppException` is built on plain `Exception`, so `ConfigurationError` arrives with its original label
and the catch matches. **That inheritance line is load-bearing:**

```python
class AppException(Exception):     # NOT ValueError
```

Rebase it on `ValueError` and pydantic repacks the error into a `ValidationError`, `main.py` stops
recognising it, and the startup banner **silently stops existing**. The app still refuses to start,
so nothing looks broken — you just quietly lose the hint and the list of valid names again.

This is worth writing down because the change is a *sensible-looking* one. Python's convention is
"a wrong value raises `ValueError`", and a bad config value is a wrong value — so a future reader may
well "tidy" that base class and feel good about it. The rule spans three places that never mention
each other: the base class in `exceptions.py`, the catch in `main.py`, and the reason, which lives in
pydantic's source. Hence the comment on the class itself.

`tests/test_logging.py::test_create_app_reports_bootstrap_failure_and_still_refuses_to_start` guards
it for free — it asserts `pytest.raises(ConfigurationError)`, which would get a `ValidationError`
instead and fail immediately.

### What was deliberately *not* done

Three rejected alternatives, recorded in full in
[`decisions/0001-bootstrap-error-reporting.md`](../decisions/0001-bootstrap-error-reporting.md):

- **Override `AppException.__str__`** to append the hint everywhere. Tempting — one line, no call-site
  change. But `describe()` already puts `str(exc)` into the `exception_message` log field *and*
  `_log_error()` already splats `log_context()` as separate fields, so every logged exception would
  carry the same data twice. **Fixing an unconfigured sink by degrading a working one is a bad trade.**
- **Format inline in `main.py`.** Correct, but teaches the app factory about stderr formatting and
  redaction. `main.py`'s value is that it's boring.
- **Configure emergency logging first, then reconfigure.** Buys a full pipeline for a window that
  produces one class of error, at the cost of a hardcoded format guess and two `logging_configured`
  events per boot.

### Known limit

A **type** error (`POSTGRES_PORT=abc`) raises pydantic's `ValidationError`, which is not an
`AppException` and so isn't caught here. That's deliberate: pydantic's own message already names the
field, the bad value and the reason, so there is no hidden context to surface. Revisit only if a real
message proves unhelpful.

---

## 10. One thing to fix later

```python
JWT_ACCESS_TOKEN_EXPIRE_DAYS: int = Field(default=30, ge=1)
```

Login passes currently last **30 days**. `AGENTIC_AI_PRODUCTION_BIBLE.md` Step 3 requires **15
minutes** plus refresh tokens and `RS256`/`EdDSA` signing — a stolen 30-day pass is a month of free
access; a stolen 15-minute one is close to worthless.

Nothing to do yet (Step 3 isn't built). But note the trap: the **unit is baked into the field name**.
You cannot express "15 minutes" in a field called `..._DAYS`, so that step needs a **rename** to
`JWT_ACCESS_TOKEN_EXPIRE_MINUTES`, not just a smaller number — and every reader moves with it. Cheap
now, while one file uses it. Annoying later, when ten do.

---

## Recap in one table

| Stage | Mechanism | The failure it prevents |
|---|---|---|
| 1 | Placeholder detection (`your-`, `mypassword`) | booting on a password that's public in git |
| 2 | `APP_ENV` from the process, not a file | the app can't find which config to load |
| 3 | Precedence cascade from `__file__` | settings silently empty depending on launch directory |
| 4 | Types + `SecretStr` | `"5432"` isn't `5432`; secrets in log lines |
| 5 | Name vs. tier lookup table | a new environment quietly missing a safety rule |
| 6 | Startup guard | debug mode, wildcard CORS, weak keys reaching production |
| 7 | `frozen` + `lru_cache` | cross-request setting mutation; untestable config |
| 8 | `Protocol` job descriptions | import cycles; hidden dependencies; heavyweight tests |
| 9 | `report_bootstrap_error()` | an error that knows the fix but never says it |
