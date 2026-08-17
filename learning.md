# Concepts & Learning Journal
## Layer 0 — Project Configuration & Dependency Management
### `pyproject.toml`

---

# Journal Entry — 2026-08-16

## Session Metadata

| Field | Value |
|---|---|
| Duration | — *(fill in)* |
| Resource | Building the 7 Layers of a Production-Grade Agentic AI System (Fareed Khan / Level Up Coding) |
| Framework / Version | uv 0.9.x, Python 3.12.7, ruff 0.15.15, mypy 2.1.0, pytest 9.1.1, pytest-asyncio 1.4.0 |
| Notebook | `pyproject.toml` *(config session — no notebook)* |
| Constraint(s) designed against | Config must be reproducible on a fresh machine and inside the Docker image with no manual steps |
| ADR(s) | — |

---

## TL;DR

- **`uv sync` is destructive, not additive** — it makes the venv *match* `pyproject.toml`, deleting anything not declared. Dev tools parked in the wrong section were being uninstalled on every sync.
- **Config that *describes* a rule ≠ a flag that *runs* it.** `fail_under = 80` and `per-file-ignores` were both well-formed and both completely inert. A gate that never fires is worse than no gate, because you stop thinking about it.
- **Declaring a package is a claim about what you import.** Four declared-but-unused deps, one missing driver variant (`psycopg[binary]`) that would have killed the persistence layer at first connect.

---

## Business / Problem Statement

`pyproject.toml` is the single source of truth for what this project *is*: its dependencies, its test rules, its lint rules, its type rules. Every other tool reads from it. When it is subtly wrong, nothing announces the problem — the tools either don't run, run against the wrong files, or run and delete your toolchain. The failures are silent by construction.

This session was a full audit: read the file, then **verify every claim by executing it** rather than reasoning about it.

**The Solution: validate config empirically, never by inspection**

TOML has no type checker. A key can be spelled correctly, placed in a valid table, and still be unreachable. The only way to know a setting is live is to make it fire.

**The workflow:**
1. **Read** — form hypotheses about what looks wrong
2. **Execute** — `--dry-run`, probe scripts, throwaway tests to prove each hypothesis
3. **Fix** — smallest change that makes the tool actually run
4. **Re-execute** — prove the fix by observing new behaviour, not by re-reading the file

---

## Phase 1 — Dependency Groups: `uv sync` Deletes What You Don't Declare
*Confidence: ?/5*

> **Iteration:** Establishes that `uv sync` is a *reconciliation* command, and that extras and dependency-groups target completely different audiences.

### Design / Architecture Decision

**Alternative considered — `[project.optional-dependencies]` (extras)**

```toml
[project.optional-dependencies]
dev = ["ruff", "mypy", "pre-commit"]
```

Extras are the **PEP 621 publishing** mechanism. They exist so a *stranger installing your package from PyPI* can opt into a flavour: `pip install yourpkg[postgres]`. They are a menu for external consumers.

**Why it was rejected:** this project sets `package = false` — it is an application, never published. There are no external consumers, so the menu is pinned to a door nobody walks through. uv does not install extras unless explicitly told `--extra dev`.

---

**Chosen approach — `[dependency-groups]` + `default-groups`** ✓

```toml
[dependency-groups]
test = ["httpx", "pytest", "pytest-cov", "pytest-asyncio"]
dev  = ["ruff", "mypy", "pre-commit"]

[tool.uv]
package = false
default-groups = ["test","dev"]
```

Dependency-groups (**PEP 735**) are the *local development* mechanism — never published, never shipped to a consumer. `default-groups` marks them always-on.

**Why this wins:**

| Concern | Tradeoff |
|---|---|
| Toolchain survives `uv sync` | Groups in `default-groups` are part of the declared state, so reconciliation keeps them |
| Correct audience | `package = false` means extras are structurally meaningless here |
| Docker still gets a lean image | Groups can be dropped at build time with `--no-default-groups` |

**The principle:** **Extras are for people who install your package. Groups are for people who develop it.** Pick by audience, not by convenience.

---

### Implementation

```
BEFORE                                    AFTER
$ uv sync --dry-run                       $ uv sync --dry-run
Would uninstall 22 packages               Would make no changes
 - pytest, pytest-cov, pytest-asyncio
 - ruff, mypy, pre-commit, coverage ...
```

**The mental model that was wrong:**

| Assumed | Actual |
|---|---|
| `uv sync` = "install what's listed" | `uv sync` = "make the venv **equal** the declared state" |
| Extra stuff in the venv is harmless | Extra stuff is **deleted** |
| Sections named `dev` behave the same | Extras and groups have different install rules |

### Prediction vs Reality

> **Expected:** the two sections were a cosmetic inconsistency — same effect, different spelling.
> **Actual:** they have different *audiences* and different install semantics. One was invisible to uv entirely.
> **Why the gap existed:** I read `[project.optional-dependencies]` and `[dependency-groups]` as synonyms because both contained a key called `dev`. The key name is the coincidence; the table is the meaning.

### Mistakes

**Mistake 1**

> **Mistake:** dev tools declared under `[project.optional-dependencies]`, test tools under `[dependency-groups]` — a split with no rationale.
> **Why tempting:** `docs/pyproject_toml_guide.md` (this repo, §1) states the dev extra is how you keep tools out of production. That's the standard folk explanation, and it's wrong for an unpublished app.
> **Failure signal:** `uv sync --dry-run` → `Would uninstall 22 packages`, followed by `pytest: command not found` after any sync.
> **Fix:** both lists into `[dependency-groups]`; `default-groups = ["test","dev"]`.

> ⚠️ **Carry-forward:** `docs/pyproject_toml_guide.md` still teaches the misconception that caused this bug. It needs correcting or it will re-teach it.

---

## Phase 2 — Abandoned Middleware: passlib Killed Itself
*Confidence: ?/5*

> **Iteration:** Establishes that an abandoned wrapper is a liability that grows over time, and that "one interface over many backends" is only worth it if you actually swap backends.

### Design / Architecture Decision

**Alternative considered — pin `bcrypt<4.1` and keep passlib**

Freezes bcrypt at a version passlib tolerates. Minimal diff, matches the article.

**Why it was rejected:** it freezes a *security* library to dodge a bug in an unmaintained wrapper. passlib's last release was 2020 — the pin can only get older and more awkward, and it blocks bcrypt security patches.

---

**Chosen approach — delete passlib, call bcrypt directly** ✓

```python
hashed = bcrypt.hashpw(password.encode(), bcrypt.gensalt())
ok     = bcrypt.checkpw(password.encode(), hashed)
```

**Why this wins:**

| Concern | Tradeoff |
|---|---|
| Security patches | bcrypt stays free to upgrade |
| Dependency count | One unmaintained package gone |
| Lost capability | passlib's algorithm-migration machinery — genuinely useful, but unused here |

**The principle:** an abstraction over one implementation is not an abstraction, it's a layer. Pay for it only when you actually swap the thing underneath.

---

### Implementation — the failure mechanism

passlib runs a self-test at `CryptContext` construction to detect a 2011-era bcrypt bug. The probe **deliberately hashes a password longer than 72 bytes**. bcrypt 5.0 treats >72 bytes as a hard error:

```
ValueError: password cannot be longer than 72 bytes
  passlib/handlers/bcrypt.py:380 in detect_wrap_bug
```

> passlib crashes inside its own safety check — a smoke detector that tests itself by starting a fire.

### Prediction vs Reality

> **Expected:** a deprecation warning. The known passlib/bcrypt issue (`bcrypt.__about__` removed in 4.1) is noisy but non-fatal.
> **Actual:** a hard `ValueError` at construction. bcrypt 5.0 escalated a second, different incompatibility from warning to error.
> **Why the gap existed:** I pattern-matched to the *famous* passlib/bcrypt bug and assumed same severity. Two different incompatibilities, two different severities.

### Mistakes

**Mistake 1**

> **Mistake:** `passlib[bcrypt]>=1.7.4` alongside `bcrypt>=4.3.0`, which resolved to bcrypt 5.0.0.
> **Why tempting:** passlib is in every FastAPI auth tutorial written before ~2024, including the article's stack.
> **Failure signal:** `ValueError: password cannot be longer than 72 bytes` on the first `CryptContext(...)` — an error whose text points at *passwords*, sending you hunting a bug in your own code that doesn't exist.
> **Fix:** removed passlib. Verified: `bcrypt 5.0.0 verify: True`.

---

## Phase 3 — Two Postgres Drivers, Neither Wired Correctly
*Confidence: ?/5*

> **Iteration:** Establishes the difference between a *declared* dependency and a *working* one, and that transitive deps can arrive incomplete.

### Implementation

`psycopg2` and `psycopg` (v3) are **different packages, not versions of each other**:

| | Old | Modern |
|---|---|---|
| Package | `psycopg2` | `psycopg` (v3) |
| Needed by | SQLAlchemy's plain `postgresql://` URL | `langgraph-checkpoint-postgres` |
| Was declared? | ✅ `psycopg2-binary` | ❌ |
| Was installed? | ✅ working | ⚠️ arrived transitively, **without libpq** |

`psycopg` v3 is only the Python half of the driver. The half that speaks Postgres's wire protocol is a C library (**libpq**) shipped in the `[binary]` variant. Without it:

```
- couldn't import psycopg 'c' implementation: No module named 'psycopg_c'
- couldn't import psycopg 'binary' implementation: No module named 'psycopg_binary'
- couldn't import psycopg 'python' implementation: libpq library not found
```

**After adding `psycopg[binary]>=3.2.0`:**

```
DRIVER OK — reached the network, failed only on connect: connection timeout expired
```

Failing on *connect* is correct with no database running. Failing on *driver load* was the bug.

### Deferred Decision

> **What was not decided:** whether to drop `psycopg2-binary` entirely.
> **Why deferred:** `config.py:66` builds a plain `postgresql://` DSN, which SQLAlchemy maps to psycopg2. Removing the driver without changing that URL breaks the DB connection, and this session was scoped to `pyproject.toml`.
> **Trigger to revisit:** when `postgres_dsn` moves to `postgresql+psycopg://` — then one driver serves both SQLAlchemy and LangGraph.

### Prediction vs Reality

> **Expected:** `psycopg2-binary` was simply redundant — the checkpointer would work off the transitively-installed `psycopg`.
> **Actual:** the transitively-installed `psycopg` **could not connect at all**. Redundancy was the lesser problem; the driver everything depends on was non-functional.
> **Why the gap existed:** I treated "package importable" as "package working." For anything wrapping a C library, those are different states.

### Mistakes

**Mistake 1**

> **Mistake:** assuming the transitive `psycopg` was usable because it imported cleanly.
> **Why tempting:** `import psycopg` succeeds. Nothing suggests a missing backend until you open a connection.
> **Failure signal:** `libpq library not found`, only reachable by actually attempting `psycopg.connect(...)`.
> **Fix:** declared `psycopg[binary]>=3.2.0` explicitly. **Directly declare anything you directly depend on — never inherit a critical dependency by accident.**

---

## Phase 4 — Inert Config: Rules That Describe vs Flags That Run
*Confidence: ?/5*

> **Iteration:** The most transferable lesson of the session. Two well-formed, correctly-spelled config blocks that had never executed once.

### Implementation

**Case A — the coverage gate**

```toml
[tool.coverage.report]
fail_under = 80        # "IF coverage runs, fail below 80%"
```

Coverage only runs when pytest is passed `--cov`. Nothing did.

```
$ uv run pytest -q | grep -c coverage
0
```

**Fix:** `addopts = ["--cov=app", "--cov-report=term-missing"]` — `addopts` injects flags into *every* pytest invocation, so the gate is on regardless of how pytest is started (Makefile, IDE, CI, bare command).

```
FAIL Required test coverage of 80.0% not reached. Total coverage: 0.00%
```

**Case B — self-cancelling ruff rules**

```toml
exclude = [..., "tests/*"]     # never open tests/
"tests/*" = ["UP"]             # while reading tests/, ignore UP   ← unreachable
```

```
$ uv run ruff check tests/
warning: No Python files found under the given path(s)
```

Test files had never been linted. **Fix:** stop excluding tests; ignore only the rule that genuinely doesn't apply:

```toml
exclude = ["migrations", "*.ipynb", ".venv"]
"tests/*" = ["UP", "S101"]
```

`S101` flags bare `assert` — a real issue in production code, because Python **strips `assert` under `-O`**, so `assert user.is_admin` silently vanishes. In a test, `assert` *is* the test. Ignore the rule, don't skip the file.

```
$ uv run ruff check tests/
All checks passed!          # and zero new errors — linting tests cost nothing
```

**The principle:** a config key being valid TOML says nothing about whether it ever executes. **Prove a setting is live by making it fire.**

### Prediction vs Reality

> **Expected:** the coverage block was working and the project was simply below 80%.
> **Actual:** it had never run. Coverage was unmeasured, not low.
> **Why the gap existed:** seeing `fail_under = 80` in the file felt like evidence the gate existed. It's evidence someone *intended* a gate.

### Mistakes

**Mistake 1**

> **Mistake:** trusting the presence of config as proof of enforcement.
> **Why tempting:** the block is correct, idiomatic, and in the right file. Nothing looks wrong.
> **Failure signal:** none — that's the whole problem. Only visible by grepping pytest output for the word "coverage" and getting `0`.
> **Fix:** wired `--cov` into `addopts`; verified the gate fired.

---

## Phase 5 — Async Tests, Unused Deps, and Latent Traps
*Confidence: ?/5*

### Implementation

**`asyncio_mode`** — an `async def` doesn't execute when called; it returns a coroutine (an IOU). Something must await it. pytest can't on its own.

```
$ uv run pytest    # bare `async def test_...()`
FAILED - Failed: async def functions are not natively supported
```

Fixed with `asyncio_mode = "auto"` → `2 passed`. Also set `asyncio_default_fixture_loop_scope = "function"` to silence a deprecation warning firing on every run — *warnings you learn to ignore are how real warnings get missed*.

**Unused dependencies** — verified absent from the codebase before deleting:

| Dropped | Reason |
|---|---|
| `tqdm` | Terminal progress bars; an API server has no terminal |
| `colorama` | Windows console colours; same |
| `asgiref` | **Transitive** via Starlette — never declare what arrives via someone else |
| `email-validator` | **Transitive** via `pydantic[email]`, also declared |

> **Direct** = you `import` it → declare it. **Transitive** = it arrives via something else → don't. Re-declaring a transitive dep lets you pin a version that fights its real owner.

**`uvicorn` → `uvicorn[standard]`** — the manual `uvloop` line with its careful `sys_platform != 'win32'` marker was correct, but `[standard]` already ships uvloop **with that identical marker**, plus `httptools` (C HTTP parser — the bigger win, since every request passes through it). Two lines → one, and gained a component.

**Latent trap — unanchored regex.** `exclude = ["migrations|evals|scripts|tests"]` reads like four folders; it's a pattern matching those words *anywhere in a path*. A future `app/services/latest_scripts.py` would be **silently skipped** by mypy. Anchored to `["^(migrations|evals|scripts|tests)/"]`. Nothing triggers it today — a landmine, not an explosion.

**`mypy python_version = "3.12"`** while `requires-python` allows 3.13 — checking against semantics you may not run. Removed; mypy now infers from the live interpreter.

### Prediction vs Reality

> **Expected:** untagged async tests would silently *skip* (green, testing nothing) — the classic pytest-asyncio trap.
> **Actual:** pytest-asyncio 1.4 **errors loudly**. The library fixed the silent-skip footgun.
> **Why the gap existed:** carried a remembered behaviour from an older version instead of checking the installed one. **Verify against the version in your lockfile, not the version in your memory.**

---

## Open Questions
*(You fill this — AI leaves blank)*

- [ ] *(2026-08-16)*
- [ ] *(2026-08-16)*
- [ ] *(2026-08-16)*

---

## Next Experiments
*(You fill this — AI leaves blank)*

Format: **verb + what + what to measure.**

- [ ]
- [ ]
- [ ]

---

## Key Takeaways Summary
*(AI drafts — confirm or edit)*

| Concept | One-liner |
|---|---|
| `uv sync` semantics | Reconciliation, not installation — it deletes anything the file doesn't declare |
| Extras vs dependency-groups | Extras serve *consumers* of a published package; groups serve *developers*. `package = false` makes extras meaningless |
| Inert config | A valid config key is not a running one — prove a setting is live by making it fire |
| Direct vs transitive deps | Declare what you import; never inherit a critical dependency by accident |
| Package extras (`[binary]`, `[standard]`) | Brackets select a *variant*, and the variant is often where the working parts live |
| Abandoned wrappers | An abstraction over one implementation is a liability that ages badly |
| Silent failure classes | The dangerous config bug isn't the one that crashes — it's the gate that never fires while you believe it does |
| Verify, don't infer | Every finding this session came from executing something; reading alone produced a wrong severity call twice |

---

## Session Retrospective

> *(AI asks: "If you were starting this today with what you know now, what would you do differently?")*

---

## Index row for `_index.md`

```
| 2026-08-16 | `pyproject.toml` | Layer 0 — dependency & tooling config audit | `uv sync` deletes undeclared packages, and valid config ≠ running config — both silent until you execute them | — |
```
