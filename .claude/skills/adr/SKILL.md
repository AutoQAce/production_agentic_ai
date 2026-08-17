---
name: adr
description: Scaffold an Architecture Decision Record before a build (or reconcile one after). Captures the constraint, ≥2 candidate architectures, a decision matrix, the choice + rationale, and predicted failure modes; writes it to decisions/ and logs a row in the root MASTER_INDEX Design Decisions Log. Use before each build project (roadmap Architect Track) and to record any real design fork. End goal: architect.
disable-model-invocation: true
---

The user wants to record an architecture decision. Arguments: $ARGUMENTS
(e.g. a decision title like "RAG retrieval strategy"; `reconcile <NNNN>` to fill actual failure modes after a build; or `list` to show existing ADRs and follow-up debt.)

## Modes

- **new** (default): scaffold a fresh ADR before building.
- **reconcile <NNNN>**: fill ADR NNNN's **Actual failure modes** from what really happened, update its Status, and refresh its Design Decisions Log row.
- **list**: list `decisions/*.md` with status and flag any ADR with Predicted but no Actual failure modes (follow-up debt).

## New ADR — instructions

### 1. Frame the decision
Parse the title/problem from $ARGUMENTS (ask if empty). Read `LEARNING_ROADMAP.md` → Architect Track to get the current **phase** and its **constraint**. If that constraint doesn't fit this specific decision, ask the user for the hard constraint to design against — never proceed without one (a decision with no constraint isn't an architecture decision).

### 2. Force real alternatives
Ask for **at least two** candidate architectures. If the user offers one, push for a genuine second (and name an obvious third if relevant). One candidate = not a decision.

### 3. Build the decision matrix
Score each candidate against cost, latency, reliability, complexity/maintainability, security, and fit-to-the-hard-constraint. Fill from the user's input; mark `?` where unknown and note it as something to measure during the build.

### 4. Decision + predicted failure modes
Record the chosen candidate and *why not the others*. Then ask: "where do you expect this to break, and how would you detect it?" — capture predicted failure modes with detection signals.

### 5. Write the ADR
Find the next number by scanning `decisions/` (NNNN, zero-padded; create the folder if missing). Create `decisions/NNNN-<slug>.md` from `adr_template.md` at the folder root, filled in.

### 6. Log it in the master Design Decisions Log
Append a row to `../MASTER_INDEX.md` → **Design Decisions Log** (replace the `*(none yet …)*` placeholder if present):
`| <date> | <title> | <phase> | <constraint> | <candidates> | <chosen + why> | <predicted failure modes> | (blank) | <patterns touched> |`
Leave **Actual (post-build)** blank — `reconcile` fills it.

### 7. Report
Confirm the ADR path and the logged row, then tell the user:
- This raises the patterns it weighs toward **D2 (selectable)**; the *chosen* pattern reaches **D3** once the decision stands under the real constraint.
- Run `/adr reconcile <NNNN>` after building — the predicted-vs-actual reconciliation is where architect judgment is actually scored.
- Run `/sync-master` (from the workspace root) to refresh the Architecture summary.

## Reconcile — instructions
Read `decisions/NNNN-*.md`. Ask what actually broke (or didn't) vs. the predictions; fill **Actual Failure Modes**, update **Status**, and update that ADR's `Actual (post-build)` cell in `../MASTER_INDEX.md` → Design Decisions Log. Note how many predictions matched — that feeds the failure-mode prediction accuracy `/sync-master` reports.

## List — instructions
List `decisions/*.md` with ADR #, title, status, and a ⚠ flag for any with Predicted but empty Actual failure modes. End with the single ADR most worth reconciling next.
