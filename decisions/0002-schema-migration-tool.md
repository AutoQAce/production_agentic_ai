# ADR-0002 — Schema migration tool: Alembic

> Architecture Decision Record. Write this **before** building (see `LEARNING_ROADMAP.md` → Architect Track).
> After the build, fill **Actual failure modes** and refresh the row in `../MASTER_INDEX.md` → Design Decisions Log.

| Field | Value |
|---|---|
| ADR # | 0002 |
| Date | 2026-09-06 |
| Status | Accepted |
| Phase | 9 (Production Infrastructure & Scale) — Step 1 foundation, consumed immediately by Step 2 |
| Notebook / module | `alembic.ini`, `migrations/env.py`, `migrations/versions/` |
| Patterns touched | schema migration, change management, database-enforced controls, deploy artifact coupling |

> **Written after the build, not before — and that is a process defect, not a formatting note.**
> `AGENTIC_AI_PRODUCTION_BIBLE.md` Step 1 names Alembic outright (*"Add Alembic now"*) and rejects no
> alternative, so the build followed the spec and a selection never happened. Two consequences, recorded
> rather than hidden: (1) an ADR was written for a six-line stderr fix (ADR-0001) while a whole
> schema-management toolchain shipped with none; (2) the Bible's own Step 1 violates this project's
> architect-track constraint of *"≥2 rejected alternatives per major component, each with the reason."*
> The analysis below was performed on challenge, after the fact. It confirms the choice — but a
> confirmation obtained after shipping is worth less than a decision made before it, and that gap is
> exactly what this template exists to close.

## Problem & Constraints

The database shape must change over time without destroying the data already in it, across four
environments (laptop, CI, staging, production), in a system where **most of the security controls are
enforced by the database rather than by application code**.

`SQLModel.metadata.create_all()` cannot do this. It creates tables that do not exist and silently ignores
tables that do — so any change to an existing table is a no-op, and the only remedy is drop-and-recreate.

- **Constraint 1:** every schema change is versioned, ordered, and reversible.
- **Constraint 2:** the tool can express **database-level controls, not just tables** — `CREATE EXTENSION`,
  revoked `UPDATE`/`DELETE` grants on the append-only audit table, per-tenant row-level security. These are
  Step 2's 🔴-finance items, and not one of them is a Python class.
- **Constraint 3:** the exact SQL can be reviewed by a human *before* it runs against a regulated database
  (EBA/ECB change-management expectations; Step 17 owns the process).
- **Constraint 4:** migrations ship in the **same build artifact** as the app, so the schema and the code
  that assumes it can never be versioned independently.
- **Constraint 5:** no second language runtime in the image.

## Candidate Architectures (≥2 — never one)

- **A — Alembic.** Python migrations, by the author of SQLAlchemy. Reads `SQLModel.metadata` directly, so
  `--autogenerate` diffs the live database against the models this project already defines.
- **B — Flyway or Liquibase.** SQL-first (Liquibase also XML/YAML), JVM-based. The incumbents in regulated
  finance; mature review and audit tooling; a DBA reviews exactly what will execute.
- **C — SQL-file runner** (golang-migrate / dbmate / Sqitch). Numbered `.sql` files applied in order and
  tracked in a version table. Single static binary, no language coupling. Sqitch adds a `verify` step.
- **D — `SQLModel.metadata.create_all()`.** The null option; the incumbent in the source article.

## Decision Matrix

Scored 1–5, higher = better.

| Criterion | A | B | C | D |
|---|---|---|---|---|
| Cost (setup + daily friction) | 5 | 2 | 4 | 5 |
| Latency *(n/a — deploy-time batch job)* | – | – | – | – |
| Reliability (code and schema cannot drift) | 5 | 3 | 3 | 1 |
| Complexity / maintainability | 4 | 2 | 4 | 5 |
| Security (Constraint 2: grants, RLS, extensions) | 4 | 5 | 5 | 1 |
| **Fit to the hard constraint** | **5** | 3 | 3 | 1 |

Note the one row A does not win. On raw expressiveness for database-level controls the SQL-first options
score higher, because in those tools *everything* is hand-written SQL and no autogenerate exists to lull
anyone into thinking the controls were handled. A scores 4 because it can express them fully through
`op.execute()` — but only when the author remembers that autogenerate will not.

## Decision

**Chosen: A (Alembic).**

**The decisive factor is Constraint 1, and it is not about SQL.** SQLModel — already this project's ORM —
is SQLAlchemy underneath, and Alembic is the only candidate that reads `SQLModel.metadata`. That makes the
Python model the single source of truth for table shape. Every other option requires hand-writing each
column change in a second place, and a second place is a place that drifts. The failure is never the first
migration; it is the two-hundredth, where someone adds a field to a model on a Friday and does not write
the matching DDL. Nothing detects that until a query fails in production.

**Why not B, despite it being the domain incumbent.** Two reasons, and the first disqualifies it. Flyway
and Liquibase are JVM tools, so adopting either means a Java runtime inside a Python image, or running
migrations from a separately-built artifact. The second option breaks Constraint 4 outright — it lets the
schema and the code that assumes it be versioned independently, which is the exact drift this decision
exists to prevent, reintroduced one layer down at deployment. The second reason is that B's headline
advantage is available in A anyway: the review-the-SQL-first workflow is `alembic upgrade head --sql`,
already wired as `migrations/env.py::run_migrations_offline`. Constraint 3 is met without the runtime.

**Why not C.** It satisfies Constraints 2, 3 and 5 well and is genuinely simpler than A. It loses on
Constraint 1 for the same reason as B — no model diffing — and adds a third-party binary to the image for
a capability A already provides. Sqitch's `verify` is the one feature none of the others has, and is worth
revisiting if migration correctness ever becomes a recurring incident source.

**Why not D.** Rejected by the spec and by arithmetic: it cannot alter an existing table at all, and its
only recovery path is data loss.

## Predicted Failure Modes

- 🔴 **Autogenerate silently omits every control that matters.** It diffs tables, columns and indexes. It
  does **not** emit `REVOKE UPDATE, DELETE` on the audit table, `ENABLE ROW LEVEL SECURITY` / `CREATE
  POLICY` for tenant isolation, `CREATE EXTENSION`, or an HNSW index method (Step 13). The failure is
  silent and shaped like success — a migration is generated, it applies cleanly, and the control is simply
  not there. → **Detect via** tests asserting the audit table has no UPDATE/DELETE grants and that RLS is
  enabled on every tenant table. Step 2's DoD already requires this; it has to be a *test*, not a review
  habit, precisely because the output looks authoritative.
- **Blind-applying generated output.** The above is only dangerous because autogenerate looks finished.
  → **Mitigate by rule:** every generated migration is read before it is applied, and the 🔴 controls are
  written by hand with `op.execute()` and literal SQL.
- **Type and nullability changes missed.** Already mitigated — `compare_type` and `compare_server_default`
  are enabled in `env.py`. Without them a `str` → `Numeric` change produces an empty migration and a schema
  that quietly disagrees with the models.
- **Python migration rot.** A migration is Python, so a file written today depends on Alembic's API
  behaving the same in two years; plain SQL files do not have this problem. → **Mitigate:** prefer literal
  SQL via `op.execute()` for the finance-critical migrations — they are the ones that must still be
  readable and re-runnable at audit time.
- **Multiple heads.** Two branches each adding a migration produce a fork needing a merge revision. Not a
  risk while solo; arrives with the second contributor. → **Detect via** `alembic heads` in CI.

## Actual Failure Modes *(fill after the build, via `/adr reconcile 0002`)*

- <what actually broke / what didn't, vs. predicted>

## Consequences

**Makes easy.** Table and column changes are a one-command draft. The model is the single source of truth
for shape. Migrations ship inside the app image, so schema and code are always the same build. Offline mode
yields a reviewable SQL artifact for Step 17's change-management story at no extra cost.

**Makes hard.** None of the database-level controls is automated, and the tool's confident output actively
disguises that. Step 2 has to treat autogenerate as a first draft and assert the controls in tests.

**Defers.** Whether finance-critical migrations standardise on literal `op.execute()` SQL rather than
Alembic's Python operations — decide at Step 2 when the audit table is actually written, not in principle
here. Multi-developer head management is deferred until there is a second developer.
