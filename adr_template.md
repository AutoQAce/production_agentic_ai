# ADR-NNNN — <Decision title>

> Architecture Decision Record. Write this **before** building (see `LEARNING_ROADMAP.md` → Architect Track).
> After the build, fill **Actual failure modes** and refresh the row in `../MASTER_INDEX.md` → Design Decisions Log.

| Field | Value |
|---|---|
| ADR # | NNNN |
| Date | YYYY-MM-DD |
| Status | Proposed / Accepted / Superseded by ADR-XXXX |
| Phase | <roadmap phase #> |
| Notebook / module | `<file>` |
| Patterns touched | <pattern A, pattern B> |

## Problem & Constraints

<What must be true? State the hard constraint you are designing against. Use the phase constraint from
the roadmap Architect Track, or a stricter one you care about. A decision with no constraint isn't an
architecture decision.>

- **Constraint:** <e.g. ≤ $0.01/query AND p95 < 2s>

## Candidate Architectures (≥2 — never one)

- **A — <name>:** <1–2 lines>
- **B — <name>:** <1–2 lines>
- **C — <name>:** *(optional)*

## Decision Matrix

Score each candidate against the constraints (e.g. 1–5, higher = better). Mark `?` where you'll only
know after measuring during the build.

| Criterion | A | B | C |
|---|---|---|---|
| Cost | | | |
| Latency | | | |
| Reliability | | | |
| Complexity / maintainability | | | |
| Security | | | |
| **Fit to the hard constraint** | | | |

## Decision

**Chosen: <A/B/C>.** <Why this one — and explicitly *why not* the others.>

## Predicted Failure Modes

Where do you expect this to break, and how would you detect it?

- <failure mode> → detect via <signal>

## Actual Failure Modes *(fill after the build, via `/adr reconcile NNNN`)*

- <what actually broke / what didn't, vs. predicted>

## Consequences

<What this decision makes easy, what it makes hard, what it defers to a later ADR.>
