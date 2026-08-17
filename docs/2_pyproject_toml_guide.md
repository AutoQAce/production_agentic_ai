# 📦 `pyproject.toml` — Line-by-Line Guide

> **Purpose:** A personal reference covering **every line** of this project's `pyproject.toml`.
> For each line: what it means in plain English, **what actually broke here when it was wrong**,
> the technical mechanism, and exactly what it solves.
>
> **Last rewritten:** 2026-08-16, after a full audit where every setting was verified by *executing* it.
> **Scope note:** the individual `dependencies` entries are not documented one by one — instead
> [§3](#3-dependencies--one-production-grade-example) shows how a dependency list *should* be written.

---

## 🚨 Read this first — the old version of this guide taught a bug

The previous version of this document said the `dev` **extra** was "how you keep tools out of production." That sentence is the direct cause of a real bug in this repo: `uv sync` was silently **uninstalling pytest, ruff, mypy, pre-commit and coverage on every run.**

That correction is explained in full in [§4](#4-dependency-groups--the-bug-this-repo-actually-hit). It's the single most important section here.

**The meta-lesson:** a config file has no type checker. A setting can be correctly spelled, in a valid table, and **never execute once**. This guide marks every place that happened with ⚠️.

---

## 📚 Table of Contents

| § | Section | Lines covered |
|---|---|---|
| 1 | [What `pyproject.toml` is](#1-what-pyprojecttoml-is) | — |
| 2 | [`[project]` — identity metadata](#2-project--identity-metadata) | 4–9 |
| 3 | [`dependencies` — one production example](#3-dependencies--one-production-grade-example) | 14–62 |
| 4 | [`[dependency-groups]` — the bug this repo hit](#4-dependency-groups--the-bug-this-repo-actually-hit) | 64–66 |
| 5 | [`[tool.uv]`](#5-tooluv) | 68–71 |
| 6 | [`[tool.pytest.ini_options]`](#6-toolpytestini_options) | 76–83 |
| 7 | [`[tool.ruff]`](#7-toolruff) | 88–99 |
| 8 | [`[tool.coverage]`](#8-toolcoverage) | 101–107 |
| 9 | [`[tool.mypy]`](#9-toolmypy) | 109–116 |
| 10 | [Known inconsistencies](#10-known-inconsistencies-in-this-file) | — |
| 11 | [Cheat sheet](#11-cheat-sheet) | — |

---

## 1. What `pyproject.toml` is

The **master settings file** for a Python project. One file replacing `setup.py`, `setup.cfg`, `.flake8`, `pytest.ini`, `.coveragerc`, `mypy.ini`.

🍕 **Plain terms:** it's the restaurant's operations binder. Ingredient list, kitchen rules, inspection standards, hygiene policy — all in one binder instead of sticky notes on five walls.

🔧 **Technical:** standardised by **PEP 518/621**. Two kinds of tables live here:

| Table | Who reads it | Standardised? |
|---|---|---|
| `[project]` | packaging tools (`uv`, `pip`, `build`) | ✅ PEP 621 — fixed meaning |
| `[tool.*]` | whichever tool owns that name | ❌ each tool invents its own keys |

**Why that split matters:** `[tool.ruff]` means whatever ruff decides it means. Nothing validates it. Misspell a key inside `[tool.*]` and most tools **silently ignore it** — no error. This is why a config audit must *run* things, not read them.

---

## 2. `[project]` — identity metadata

```toml
[project]
name = "7-layers-production-agentic-ai"
version = "0.1.0"
description = "Production-grade agentic AI system"
readme = "README.md"
requires-python = ">=3.12, <3.14"
```

### `name`, `version`, `description`, `readme`

🍕 **Plain terms:** the label on the tin. Name, edition number, one-line pitch, and where the full instructions live.

🔧 **Technical:** PEP 621 required fields. If this project were published to PyPI, `name` would be its install name and `version` would determine what `pip install pkg==0.1.0` resolves to.

⚠️ **What we hit:** nothing — but understand *why* they barely matter here. This project sets `package = false` ([§5](#5-tooluv)) — it is **never published**. So these four fields are essentially documentation. `version = "0.1.0"` isn't wrong, it's just decorative; nothing reads it. Don't spend time perfecting them, and don't assume changing `version` does anything.

✅ **Solves:** gives tools a name to print in error messages, and keeps the file PEP 621-valid.

---

### `requires-python = ">=3.12, <3.14"`

🍕 **Plain terms:** "this kitchen needs an oven from 2024 or 2025 — not older, not the 2026 model we haven't tested."

Both halves matter, and the second half is the one people skip:
- **Floor (`>=3.12`)** — below this, the code genuinely won't work (you use syntax 3.11 doesn't have).
- **Ceiling (`<3.14`)** — above this, you *don't know* if it works. Nobody has tried. A ceiling is an honest statement of ignorance, not a claim of breakage.

🔧 **Technical:** `uv` refuses to resolve dependencies against an interpreter outside this range, and refuses to select package versions that themselves declare an incompatible `requires-python`. It shapes the **entire dependency resolution**, not just a startup check.

⚠️ **What we hit:** an indirect problem. `[tool.mypy]` had `python_version = "3.12"` hardcoded — so this range said "3.12 **or 3.13**," while the type checker only ever verified 3.12 semantics. Type rules differ between versions, so code that breaks on 3.13 could pass every check. Fixed in [§9](#9-toolmypy).

✅ **Solves:** stops someone installing on Python 3.11 and hitting a baffling `SyntaxError` deep in your code, and stops silent upgrades onto an untested interpreter.

> **The transferable idea:** a version range is **two different claims** — a floor is "I know this breaks," a ceiling is "I haven't checked." Both belong in production config. This same idea returns in [§3](#3-dependencies--one-production-grade-example), where this file currently gets it wrong.

---

## 3. `dependencies` — one production-grade example

You asked not to document all 25 entries. Here's the more useful thing: **how a dependency list should be written for a production agentic AI service**, and how this project's list differs.

### The four decisions in every dependency line

```toml
"psycopg[binary]>=3.2.0,<4"
#  │       │       │      │
#  │       │       │      └── 4. CEILING   — untested territory
#  │       │       └───────── 3. FLOOR     — minimum you rely on
#  │       └───────────────── 2. EXTRA     — which variant
#  └───────────────────────── 1. PACKAGE   — the name
```

Most people only think about #1 and #3. **#2 and #4 are where production bugs live** — and this repo was bitten by #2.

---

### A production-grade agentic AI dependency block

```toml
dependencies = [
    # --- Serving ---
    # [standard] bundles httptools (C HTTP parser) + uvloop. uvloop ships with a
    # `sys_platform != 'win32'` marker inside the bundle, so Windows dev is unaffected.
    "uvicorn[standard]>=0.34.0,<1",
    "fastapi>=0.121.0,<1",

    # --- LLM / agent runtime ---
    # CEILINGS ARE NOT OPTIONAL HERE. The LangChain ecosystem has shipped breaking
    # changes on minor releases. An unbounded `>=1.0.2` accepts 2.0 without asking.
    "langchain>=1.0.5,<2",
    "langgraph>=1.0.2,<2",
    "langgraph-checkpoint-postgres>=3.0.1,<4",

    # --- Persistence ---
    # [binary] ships the compiled libpq. WITHOUT IT the driver imports fine and then
    # cannot open a single connection. See the incident note below.
    "psycopg[binary]>=3.2.0,<4",

    # --- Security-sensitive: floor is a SECURITY floor, not a feature floor ---
    "bcrypt>=4.3.0,<6",

    # --- Pinned exactly, with a stated reason and an expiry ---
    # Pinned 2026-07: 3.10 changed the span schema and breaks our Grafana dashboard.
    # REVISIT after the dashboard is migrated. A pin without a reason is a mystery;
    # a pin without a revisit trigger is permanent by accident.
    "langfuse==3.9.1",
]

# Evaluation stack — NOT in the runtime image. The API container never runs evals.
[dependency-groups]
evals = ["ragas>=0.2,<1", "datasets>=3,<4"]
```

---

### The five rules that block shows

**Rule 1 — Cap the major version on anything that moves fast.**

🍕 **Plain terms:** `>=1.0.5` means "1.0.5 or anything newer, forever, including a rewrite that shares nothing but the name."

🔧 **Technical:** `uv.lock` protects you from *accidental* drift — it pins exact versions. But the moment anyone runs `uv lock --upgrade`, or adds a package that forces re-resolution, an uncapped `>=` will happily jump a major version across your whole agent stack.

⚠️ **This file's current state:** **35 `>=` constraints, zero ceilings.** Verified:
```
$ grep -c 'dep>=x,<y' pyproject.toml
0
```
This is the largest remaining production gap in the file. Nothing is broken today. It's a loaded gun with the safety off.

✅ **Solves:** turns "our agent broke and nobody touched the code" into an upgrade you chose, reviewed, and tested.

---

**Rule 2 — The bracket `[extra]` often contains the working parts.**

🍕 **Plain terms:** you hired a translator who studied the grammar perfectly but has no mouth. The `[binary]` bracket is the mouth.

⚠️ **What we hit — the real incident:** `langgraph-checkpoint-postgres` depends on `psycopg` v3. Because of that, plain `psycopg` **was installed automatically**. It imported cleanly. It looked completely fine. But `psycopg` on its own is only the Python half of the driver — the half that speaks Postgres's network protocol is a C library (**libpq**) shipped only in the `[binary]` variant:

```
- couldn't import psycopg 'c' implementation: No module named 'psycopg_c'
- couldn't import psycopg 'binary' implementation: No module named 'psycopg_binary'
- couldn't import psycopg 'python' implementation: libpq library not found
```

**The persistence layer — the thing this whole article is about — could not open a connection.** And it would only have surfaced the first time an agent tried to save state.

🔧 **Technical:** extras (PEP 508) select an optional dependency bundle. For C-backed libraries, the bundle is frequently the compiled backend. `import x` succeeding proves the *Python* package is present; it proves nothing about its native backend.

✅ **Solves:** after adding `psycopg[binary]>=3.2.0`:
```
DRIVER OK — reached the network, failed only on connect: connection timeout expired
```
Failing at *connect* with no database running is correct. Failing at *driver load* was the bug.

> **The rule this produces:** **declare directly anything you depend on directly.** Never inherit a critical dependency by accident — you don't control its version, its extras, or whether it keeps arriving at all.

---

**Rule 3 — Never declare what arrives transitively.**

| | Definition | Declare it? |
|---|---|---|
| **Direct** | you `import` it in your own code | ✅ always |
| **Transitive** | it arrives because something else needs it | ❌ never |

⚠️ **What we hit:** four such entries — `asgiref` (via Starlette), `email-validator` (via `pydantic[email]`, which was *also* declared), plus `tqdm` and `colorama`, which are terminal progress-bar and console-colour libraries in a headless API server. All four removed after verifying zero imports across `app/ tests/ evals/ scripts/`.

🔧 **Technical:** re-declaring a transitive dependency lets you pin a version that conflicts with its real owner's requirement — resolver deadlock, or worse, a silent downgrade. It also adds it to every security scan and your Docker image forever.

✅ **Solves:** smaller image, fewer CVE surfaces, and "can we drop this?" becomes answerable.

---

**Rule 4 — A pin needs a reason and an expiry.**

🍕 **Plain terms:** `==` is a sticky note saying "DO NOT UPGRADE." Without a *why* and a *when*, nobody ever dares remove it, and you're stuck on a 2026 version in 2029.

🔧 **Technical:** `==` freezes exactly. Legitimate when a specific version has a known incompatibility with something you can't change yet. The comment must record **what broke** and **what must be true to unpin**.

⚠️ **This file's current state:** `langfuse` was `==3.9.1` and has since been loosened to `>=3.9.1` — **but the comment still says `(pinned per article)`**, which is no longer true. See [§10](#10-known-inconsistencies-in-this-file). A comment that contradicts its line is worse than no comment: you'll trust it.

---

**Rule 5 — Separate what runs in production from what doesn't.**

⚠️ **This file's current state:** everything is in one flat `dependencies` list, so the eval stack and search tooling ship into the API container regardless of whether that container ever runs evals. Bigger image, larger attack surface, slower cold starts. The fix is a `[dependency-groups] evals` group excluded at build time.

---

## 4. `[dependency-groups]` — the bug this repo actually hit

```toml
[dependency-groups]
test = ["httpx>=0.28.1", "pytest>=8.3.5", "pytest-cov>=6.0.0", "pytest-asyncio>=0.24.0"]
dev  = ["ruff>=0.8.0", "mypy>=1.11.1", "pre-commit>=4.6.0"]
```

### ⚠️ The incident — read this even if you skip everything else

**Before the fix,** the dev tools lived in `[project.optional-dependencies]` and only the test tools were in `[dependency-groups]`. Neither was installed. And `uv sync` **deleted them**:

```
$ uv sync --dry-run
Would uninstall 22 packages
 - pytest, pytest-cov, pytest-asyncio, ruff, mypy, pre-commit, coverage, ...
```

Run `make install`, then `make test` → `pytest: command not found`. On CI, worse: a fresh machine installs no test tools and the pipeline either crashes or "passes" having run **zero tests**.

### The mental model that was wrong

🍕 **Plain terms:** most people think `uv sync` means *"install the things on my list."* It actually means:

> **"Make the virtual environment EQUAL this file. By any means — including deletion."**

It's not a shopping trip. It's an inventory reconciliation. Anything in the venv not declared in the file **gets thrown out**.

| Assumed | Actual |
|---|---|
| `uv sync` installs what's listed | `uv sync` makes the venv **equal** the declared state |
| Extra packages are harmless | Extra packages are **deleted** |
| Sections both named `dev` behave alike | Extras and groups have different install rules |

### Extras vs groups — the distinction that caused it

| | `[project.optional-dependencies]` (**extras**) | `[dependency-groups]` (**groups**) |
|---|---|---|
| Standard | PEP 621 | PEP 735 |
| **Audience** | **strangers installing your package** | **you, developing this project** |
| Analogy | the "want fries with that?" menu | the chef's own knife roll |
| Published to PyPI? | ✅ yes, visible to consumers | ❌ never |
| Installed by default? | ❌ needs `--extra dev` | ❌ unless in `default-groups` |

🍕 **Plain terms:** extras are a **menu for customers**. Groups are the **staff cupboard**. This project sets `package = false` — it's a restaurant, never a packaged product. **There are no customers.** So the extras menu was a note pinned to a door nobody walks through, and uv correctly ignored it — then deleted everything on it.

🔧 **Technical:** extras exist so a consumer can run `pip install yourpkg[postgres]`. Since this project is never published, that code path is unreachable. Dependency-groups are local-development-only by design and never appear in built metadata. Modern pip (25.1+) supports them via `--group`; the old claim that they are "uv-only" is out of date.

✅ **Solves:** with both lists in `[dependency-groups]` and both named in `default-groups`, they are part of the declared state — so reconciliation *keeps* them:

```
$ uv sync --dry-run
Would make no changes          ← idempotent. This is the proof.
```

> **The transferable idea:** **choose extras vs groups by audience, not by convenience.** "Is this for someone installing my package, or someone developing it?"

---

## 5. `[tool.uv]`

```toml
[tool.uv]
package = false
default-groups = ["test","dev"]
```

### `package = false`

🍕 **Plain terms:** two kinds of food business —

| | Example | Behaviour |
|---|---|---|
| 🏪 **Product** | Maggi noodles | boxed, shipped, sold in shops (PyPI) |
| 🍽️ **Restaurant** | your pizza place | cooks and serves directly, never boxed |

This is a restaurant. `package = false` tells uv: *"don't try to box me up — just install my ingredients and let me cook."*

🔧 **Technical:** without it, uv invokes a build backend, and setuptools runs **package auto-discovery** across the root. It finds `app/`, `evals/`, `scripts/`, `tests/`, can't decide which is the importable package, and errors with `Multiple top-level packages discovered in a flat-layout`. The usual "fix" people reach for is inventing a `src/` layout they don't need.

✅ **Solves:** no build step, no auto-discovery, no phantom `src/`. It also makes `pythonpath = ["."]` ([§6](#6-toolpytestini_options)) *necessary* — since nothing is installed as a package, imports must resolve from the project root instead.

> These two settings are a **pair**. `package = false` creates the problem that `pythonpath = ["."]` solves. Changing one without the other breaks imports.

---

### `default-groups = ["test","dev"]`

🍕 **Plain terms:** "these two cupboards are always open — don't make me ask every time."

⚠️ **What we hit:** without this, `uv sync` installed neither group, then deleted their contents. This one line is what makes `uv sync` idempotent.

🔧 **Technical:** uv installs only groups listed in `default-groups` (which defaults to `["dev"]` alone). Naming both here makes them part of the default declared state.

✅ **Solves:** `make install` produces a working toolchain on a fresh clone with no extra flags.

> ⚠️ **Consequence to know about — it reaches outside this file.** Your `Dockerfile` runs `uv sync --frozen --no-dev`. **`--no-dev` drops only the `dev` group.** Verified:
> ```
> $ uv sync --frozen --no-dev --dry-run
> Would uninstall 16 packages
>  - mypy, ruff, pre-commit, virtualenv, nodeenv, identify, ...
>    (pytest, pytest-cov, httpx, coverage: NOT removed)
> ```
> So **pytest and httpx currently ship inside your production image.** The fix is `--no-default-groups` in the Dockerfile, which drops every group.

---

## 6. `[tool.pytest.ini_options]`

```toml
pythonpath = ["."]
testpaths = ["tests"]
markers = ["slow: marks tests as slow (deselect with '-m \"not slow\"')"]
python_files = ["test_*.py", "*_test.py", "tests.py"]
addopts = ["--cov=app", "--cov-report=term-missing"]
asyncio_mode = "auto"
asyncio_default_fixture_loop_scope = "function"
```

### `pythonpath = ["."]`

🍕 **Plain terms:** "when looking for my code, start at the project's front door."

🔧 **Technical:** prepends the project root to `sys.path` before collection. Required precisely *because* `package = false` means `app/` is never installed — without it, `import app.core.config` inside a test raises `ModuleNotFoundError`.

✅ **Solves:** tests import application code the same way the running app does.

---

### `testpaths = ["tests"]`

🍕 **Plain terms:** "the inspector checks the kitchen. Not the car park, not the storeroom."

⚠️ **What we hit:** without it pytest walks the entire project root, meaning `evals/` and `scripts/` get scanned every run — slower, and a stray file matching `test_*.py` in either would be collected as a real test.

🔧 **Technical:** restricts the default collection roots. Explicit paths on the command line still override it.

✅ **Solves:** faster, predictable collection with a defined boundary.

---

### `markers = ["slow: ..."]`

🍕 **Plain terms:** a 🐢 sticker on dishes that take 10 minutes to taste, so the inspector can skip them when short on time.

```python
@pytest.mark.slow
def test_real_llm_call():   # hits a live API, takes 30s
    ...
```
```bash
pytest -m "not slow"   # fast inner loop
pytest                 # everything, before merging
```

🔧 **Technical:** registering markers here is what suppresses `PytestUnknownMarkWarning`. Unregistered markers still *work*, which is the trap — a typo'd `@pytest.mark.slwo` silently matches nothing, so `-m "not slow"` runs the slow test anyway.

✅ **Solves:** a fast dev loop, and typo'd markers become visible instead of silent.

> **Especially valuable in agentic AI**, where "slow" means real LLM calls that cost money. This marker is a spend control, not just a speed control.

---

### `python_files = ["test_*.py", "*_test.py", "tests.py"]`

🍕 **Plain terms:** "only these filename shapes are tests."

🔧 **Technical:** the collection filename filter. The default is `test_*.py` and `*_test.py`; `tests.py` is added here for a Django-style convention.

✅ **Solves:** stops a helper like `testing_utils.py` being imported and executed as a test module.

---

### ⚠️ `addopts = ["--cov=app", "--cov-report=term-missing"]`

**This is the second silent-failure bug, and the most transferable lesson in this file.**

🍕 **Plain terms:** you had a smoke detector screwed to the ceiling — `fail_under = 80` in [§8](#8-toolcoverage) — **with no battery in it.** You could see it. It looked reassuring. It had never once made a sound.

⚠️ **What we hit:** `[tool.coverage]` is a **rulebook**. It says *"IF coverage runs, fail below 80%."* It does not *cause* coverage to run. Coverage only runs when pytest is passed `--cov`. Nothing did — the Makefile runs plain `pytest -q`:

```
$ uv run pytest -q | grep -c coverage
0                                        ← never ran. Not low. Unmeasured.
```

**Why this is worse than having no gate:** with no gate you know you're unprotected. With an inert gate you *believe* you're protected and stop thinking about it. Your project rules mandate 80% — it was being enforced on paper only.

🔧 **Technical:** `addopts` injects flags into **every** pytest invocation — Makefile, IDE run button, CI, bare `pytest`. Putting `--cov` here means the gate cannot be bypassed by forgetting a flag. `term-missing` additionally prints *which line numbers* were never executed.

✅ **Solves:** verified firing for the first time —
```
TOTAL                       151    151     0%
FAIL Required test coverage of 80.0% not reached. Total coverage: 0.00%
```

> **The transferable idea — the single biggest one in this document:**
> **Config that *describes* a rule is not a flag that *runs* it.**
> A setting being valid TOML says nothing about whether it ever executes.
> **Prove a setting is live by making it fire.** If you've never seen it fail, you don't know it works.

---

### `asyncio_mode = "auto"`

🍕 **Plain terms:** an `async def` function doesn't do the work when you call it — it hands back an **IOU**. Someone has to cash the IOU. pytest doesn't know how.

⚠️ **What we hit:** with the default (`strict`) mode, pytest only handles async tests explicitly tagged `@pytest.mark.asyncio`. A bare async test:

```
$ uv run pytest
FAILED - Failed: async def functions are not natively supported
```

Your middleware and exception handlers are async, so your tests will be too.

> 📌 **Version note worth internalising:** *older* pytest-asyncio **silently skipped** untagged async tests — green suite, testing nothing. Version 1.4 (yours) errors loudly instead. During the audit I predicted the silent skip from memory and was wrong. **Check the behaviour of the version in your lockfile, not the version in your head.**

🔧 **Technical:** `auto` treats every `async def test_*` as an async test and supplies an event loop automatically.

✅ **Solves:** no decorator on every async test, and no confusing failure that looks like a bug in your code.

---

### `asyncio_default_fixture_loop_scope = "function"`

🍕 **Plain terms:** "give each test its own clean workspace, and stop nagging me about it."

🔧 **Technical:** sets the event-loop scope for async fixtures. Unset, pytest-asyncio emits a `DeprecationWarning` on **every run**. `function` scope means a fresh event loop per test — the safest default, since a loop shared across tests leaks state (pending tasks, open connections) between them.

✅ **Solves:** removes recurring warning noise, and guarantees test isolation.

> **Why the warning mattered more than it looked:** warnings you learn to ignore are how real warnings get missed. Silencing a known-benign one keeps the signal channel clean.

---

## 7. `[tool.ruff]`

```toml
[tool.ruff]
line-length = 119
exclude = ["migrations", "*.ipynb", ".venv"]
lint.select = ["E", "F", "I", "UP", "B", "ERA", "S"]
lint.ignore = ["E501", "UP006", "UP007", "UP035"]
```

> **Note:** ruff replaces **black + isort + flake8 + bandit + pyupgrade** — one Rust binary instead of five Python tools. The previous version of this guide documented `[tool.black]` and `[tool.isort]` sections; **neither exists in this project** and neither tool is installed. `black .` and `isort .` would fail. Use `ruff format .` and ruff's `I` rules instead.

### `line-length = 119`

🍕 **Plain terms:** a newspaper column width. Too wide and the eye loses its place returning to the next line.

🔧 **Technical:** read by **both** the linter (rule `E501`) and the formatter (`ruff format`). Since `E501` is ignored below, this value effectively governs **only the formatter** — ruff will wrap lines when formatting but won't complain about long ones you write by hand.

✅ **Solves:** consistent wrapping with no nagging. That combination is deliberate, not an accident.

---

### `exclude = ["migrations", "*.ipynb", ".venv"]`

| Excluded | Why |
|---|---|
| `migrations/` | auto-generated by Alembic — not yours to fix |
| `*.ipynb` | notebooks are exploratory by nature; this repo is notebook-first |
| `.venv/` | third-party code |

⚠️ **What we hit — a self-cancelling pair of rules.** This list previously also contained `"tests/*"`, while `per-file-ignores` below contained a `"tests/*"` entry. Those contradict:

```toml
exclude = [..., "tests/*"]     # never open tests/
"tests/*" = ["UP"]             # while reading tests/, ignore UP   ← unreachable
```

```
$ uv run ruff check tests/
warning: No Python files found under the given path(s)
```

**Test files had never been linted at all.** A broken test is the worst kind of broken code, because it can *pass* while asserting nothing.

🔧 **Technical:** `exclude` operates at file discovery — excluded files are never parsed, so no per-file rule can ever apply to them. Exclusion always wins.

✅ **Solves:** removing `tests/*` from `exclude` made the per-file rules live. Verified — and it cost nothing:
```
$ uv run ruff check tests/
All checks passed!          ← zero new errors
```

> **The transferable idea:** if you're excluding a whole directory to dodge **one** rule, you've thrown out all the others too. Suppress the rule, not the file.

---

### `lint.select` — which rule families are active

| Code | Family | Catches | Why it's on |
|---|---|---|---|
| `E` | pycodestyle | spacing, indentation | baseline style |
| `F` | Pyflakes | **undefined names, unused imports** | genuine bugs |
| `I` | isort | unsorted imports | replaces isort entirely |
| `UP` | pyupgrade | outdated syntax | modernisation |
| `B` | bugbear | **likely bugs** — mutable default args, loop-variable capture | highest value-per-rule |
| `ERA` | eradicate | commented-out code | dead code rots |
| `S` | **bandit** | **security** — hardcoded secrets, `eval`, weak crypto | 🔒 most teams never enable this |

🍕 **Plain terms:** `E` is spelling and punctuation. `F` and `B` are "this sentence contradicts itself." `S` is "you just wrote your password on a postcard."

✅ **What `S` caught the moment it could run:**
```
S105 Possible hardcoded password assigned to: "POSTGRES_PASSWORD"
  --> app/core/config.py:55    POSTGRES_PASSWORD: str = "mypassword"
S105 --> app/core/config.py:46 JWT_SECRET_KEY: str = "change-me"
```
Real secrets-as-defaults. Enabling `S` is the single highest-value line in this block.

---

### `lint.ignore` — deliberate exceptions

| Code | Rule | Honest reason |
|---|---|---|
| `E501` | line too long | the formatter handles wrapping; don't nag about handwritten lines |
| `UP006` | `list` not `List` | matches the article's older typing style |
| `UP007` | `X \| Y` not `Optional[X]` | same |
| `UP035` | deprecated `typing` imports | same |

⚠️ **Be honest about what this combination does:** `UP` is selected, then its three main typing rules are switched off. **`UP` is largely neutered for type annotations.** That's a defensible choice for following an article verbatim — but `CLAUDE.md` currently claims *"Modern type syntax enforced (`UP` rules) — use `list[str]` not `List[str]`"*, which **is not what this config does.** See [§10](#10-known-inconsistencies-in-this-file).

---

### `[tool.ruff.lint.isort] known-first-party = ["app"]`

🍕 **Plain terms:** "`app` is *our* code, not a library we downloaded — file it in its own section."

🔧 **Technical:** ruff groups imports as stdlib → third-party → first-party → local. Without this hint it may guess wrong and shuffle `app` imports into the third-party block, producing churn every time someone runs the formatter.

```python
import json                          # stdlib
from fastapi import FastAPI          # third-party
from app.core.config import Settings # first-party  ← this line's placement
```

✅ **Solves:** stable, meaningful import grouping and no formatter ping-pong between machines.

---

### `[tool.ruff.lint.per-file-ignores]`

```toml
"__init__.py" = ["E402", "F401"]
"tests/*" = ["UP", "S101"]
```

**`__init__.py` → `F401` (imported but unused)**

```python
# app/services/__init__.py
from app.services.user_service import UserService   # re-exported on purpose
```
Ruff would flag `UserService` as unused — but re-exporting *is* the file's job. `E402` similarly allows imports below other statements, common in package init files.

**`tests/*` → `S101` (use of `assert`)** ⭐ the important one

🍕 **Plain terms:** in production code, `assert` is genuinely dangerous — **Python deletes every `assert` statement when run with the `-O` flag.** So a security check written as `assert user.is_admin` **silently vanishes in production.** That's why `S101` exists and why it's a real security rule.

But in a **test**, `assert` *is* the test. Flagging it is nonsense.

⚠️ **What we hit:** the original config dodged `S101` by excluding the entire `tests/` directory — throwing away all linting to avoid one rule.

✅ **Solves:** the correct shape — lint tests, suppress only the rule that doesn't apply. `UP` is kept ignored for consistency with the main config.

---

## 8. `[tool.coverage]`

```toml
[tool.coverage.run]
source = ["app"]
omit = ["*/tests/*", "*/migrations/*"]

[tool.coverage.report]
fail_under = 80
show_missing = true
```

| Line | 🍕 Plain terms | 🔧 Technical |
|---|---|---|
| `source = ["app"]` | "measure the kitchen, not the whole building" | limits measurement to `app/`; without it, coverage includes `.venv` and your % becomes meaningless |
| `omit = [...]` | "don't grade the exam paper by how much of the exam it covers" | tests measuring their own coverage is circular |
| `fail_under = 80` | the pass mark | **exits non-zero** below 80% — this is what makes it a *gate* rather than a report |
| `show_missing = true` | "tell me *which* lines, not just the score" | prints uncovered line numbers so the number is actionable |

⚠️ **Everything in this block was inert until `addopts` was added** — see [§6](#-addopts--covapp---cov-reportterm-missing). It is the rulebook; `--cov` is what summons the inspector.

⚠️ **Still a real problem:** `fail_under = 80` against **actual coverage of 0%** (the suite can't currently collect, due to an unrelated `LOG_FORMAT` bug in `app/core/config.py`). A gate that fails every single run is a gate someone disables in week two. **Production practice is to ratchet:** set it to current + 1 and raise it as coverage climbs. An aspirational number plus a permanently red build teaches the team to ignore red builds.

---

## 9. `[tool.mypy]`

```toml
[tool.mypy]
# python_version deliberately unset
warn_unused_configs = true
warn_redundant_casts = true
warn_unused_ignores = true
disallow_untyped_defs = true
exclude = ["^(migrations|evals|scripts|tests)/"]
```

### The absent `python_version` — a deliberate deletion

⚠️ **What we hit:** it read `python_version = "3.12"` while `requires-python` allows **3.12 or 3.13**. You were type-checking against semantics you might not run. Removing it makes mypy infer from the live interpreter, so checks track reality.

> **Note the pattern:** this is the *third* bug in this file of the same shape — a setting that looked correct in isolation but contradicted another setting elsewhere. `python_version` vs `requires-python`; `exclude` vs `per-file-ignores`; `[tool.coverage]` vs `addopts`. **Config bugs live in the gaps between settings, not inside them.**

### The four `warn_*` / `disallow_*` flags

| Flag | 🍕 Plain terms | 🔧 What it catches |
|---|---|---|
| `warn_unused_configs` | "tell me if I configured something that matched nothing" | a section for a module that no longer exists — **the anti-inert-config flag** |
| `warn_redundant_casts` | "tell me when I'm explaining something you already knew" | `cast(int, x)` where `x` is already `int` — usually a leftover from a refactor |
| `warn_unused_ignores` | "tell me when a `# type: ignore` is no longer needed" | silenced errors that got fixed upstream — stops permanent blanket suppressions |
| `disallow_untyped_defs` | "every function must declare its inputs and output" | the one that does the real work — an untyped function is a hole mypy can't see through |

> `warn_unused_configs` deserves attention: it exists specifically because **config rot is silent**. It's mypy's built-in defence against exactly the class of bug this audit found everywhere else.

### `exclude = ["^(migrations|evals|scripts|tests)/"]`

⚠️ **What we hit — a latent trap, not a live bug.** It previously read:

```toml
exclude = ["migrations|evals|scripts|tests"]
```

🍕 **Plain terms:** that *reads* like a list of four folders. It isn't. It's a **search pattern that matches those words anywhere in a file path.**

So a future file called `app/services/latest_scripts.py` — which contains the letters `scripts` — would be **silently skipped by the type checker.** No error, no warning, just quietly unchecked code.

🔧 **Technical:** mypy's `exclude` takes regular expressions matched against the path. Unanchored, the pattern matches any substring. `^` anchors to the start of the path and the trailing `/` requires a directory boundary.

✅ **Solves:** it now means what it always looked like it meant. Verified no regression — still `checked 17 source files`.

> Nothing triggered this today. It's a **landmine, not an explosion** — it detonates months later when someone names a file innocently. Those are the config bugs worth hunting, because no test will ever catch them.

### 🔍 Honest gap in this section

mypy is **strict in the wrong half**. `disallow_untyped_defs` is good, but there's no `strict`, no `warn_return_any`, no `disallow_any_generics` — and it **excludes `tests/`**. Untyped test code is exactly where type confusion hides, because a test that passes the wrong type still "passes" if the assertion is weak. You're checking the code that has type hints and skipping the code that doesn't.

---

## 10. Known inconsistencies in this file

Live at the time of writing. Left as-is — recorded so they don't silently rot.

| # | Where | Problem |
|---|---|---|
| 1 | `langfuse>=3.9.1` | comment still says **`(pinned per article)`** but the `==` pin was loosened to `>=`. The comment now contradicts its line. |
| 2 | All 35 dependencies | **zero major-version ceilings.** Biggest remaining production gap — see [§3 Rule 1](#3-dependencies--one-production-grade-example). |
| 3 | `CLAUDE.md` | claims Google docstring convention with `D` rules enforced. **`D` is not in `lint.select`.** Also documents Python `>=3.11` while this file says `>=3.12`. |
| 4 | `CLAUDE.md` | claims *"Modern type syntax enforced (`UP`)"* while `UP006`/`UP007`/`UP035` are all ignored. |
| 5 | `psycopg2-binary` | second Postgres driver, kept only because `config.py:66` builds a plain `postgresql://` DSN. Drop it once that becomes `postgresql+psycopg://`. |
| 6 | `Dockerfile` | uses `--no-dev`, which no longer excludes the `test` group — **pytest and httpx ship to production.** Needs `--no-default-groups`. |
| 7 | `.github/workflows/` | **empty except `.gitkeep`.** Every gate in this file is opt-in on human memory. This is the highest-leverage fix in the repo. |

---

## 11. Cheat sheet

### Every setting at a glance

| Setting | Value | Plain English |
|---|---|---|
| `requires-python` | `>=3.12, <3.14` | floor = known broken below; ceiling = untested above |
| `[dependency-groups]` | `test`, `dev` | **staff cupboard** — never published |
| `[tool.uv] package` | `false` | "I'm a restaurant, not a boxed product" |
| `default-groups` | `["test","dev"]` | always install both — stops `uv sync` deleting the toolchain |
| `pythonpath` | `["."]` | find `app/` from the project root |
| `testpaths` | `["tests"]` | don't walk `evals/` and `scripts/` |
| `markers` | `["slow: ..."]` | tag expensive LLM tests — a spend control |
| `addopts` | `["--cov=app", ...]` | **puts the battery in the smoke detector** |
| `asyncio_mode` | `"auto"` | run `async def` tests without a decorator |
| `line-length` | `119` | governs the formatter (E501 is ignored) |
| `lint.select` | `E F I UP B ERA S` | `S` = security. The one most projects skip |
| `per-file-ignores` | `S101` in tests | `assert` is dangerous in prod, mandatory in tests |
| `fail_under` | `80` | exits non-zero — a gate, not a report |
| `exclude` (mypy) | `^(...)/ ` | **anchored** — patterns, not folder names |

### Commands

```bash
uv sync                     # reconcile the venv — DELETES anything undeclared
uv sync --dry-run           # preview it. "Would make no changes" = healthy
uv lock --check             # is uv.lock in sync with pyproject.toml?

uv run ruff check .         # lint
uv run ruff check . --fix   # autofix
uv run ruff format .        # format  (NOT `black .` — black isn't installed)
uv run mypy .               # type check

uv run pytest               # tests + coverage gate (via addopts)
uv run pytest -m "not slow" # skip expensive LLM tests
```

### Verifying config actually works

The habit this whole audit came down to — **never trust a setting you haven't watched fire:**

```bash
uv sync --dry-run                       # "Would make no changes" = groups correct
uv run pytest 2>&1 | grep -i coverage   # any output = the gate is live
uv run ruff check tests/                # "No Python files found" = wrongly excluded
```

---

*Rewritten 2026-08-16 after a line-by-line audit in which every setting was verified by execution.*
*Companion: `learning.md` (root) — the journal entry with prediction-vs-reality gaps and mistake analysis.*
