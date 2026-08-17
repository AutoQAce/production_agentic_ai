# Concepts & Learning Journal
## <Topic / Pillar Title>
### `<notebook_filename.ipynb>`

---

## ⚡ Tired or short on time?
**[Jump straight to Quick Entry ↓](#quick-entry----yyyy-mm-dd)** — 3 questions, under 2 minutes. Promote to full entry later.

---

## How to Use This Journal

**Fresh entry** (no prior content for this notebook today): include the Business / Problem Statement, then phases numbered from 1.
**Appending** (entry already exists for today): add the next phase block. Phase numbers reset per day — use the date as the outer key, not a global counter.
**Tired / short on time**: jump to Quick Entry at the bottom of this file.

### What AI Will and Won't Do

| Section | AI Behaviour |
|---|---|
| Phase content | Uses best format — prose, table, diagram, ASCII flow, or code |
| Considered Alternative | Always asks "what else did you consider?" even briefly |
| Deferred Decisions | Asks "anything you chose not to decide yet?" after each phase |
| Confidence gap | If rating ≤ 2, asks "what specifically feels shaky?" |
| Mistakes | Asks four clarifying questions first; writes nothing until you answer |
| Multiple mistakes | Repeats the four-question cycle for each mistake in a phase |
| Prediction vs Reality | Prompts after each phase; skips if expectations matched |
| Continuity links | Asks "does this phase build on anything from a previous entry?" |
| Session retrospective | Asks one meta-question at the very end of each session |
| Open Questions | You fill. AI leaves blank. |
| Next Experiments | You fill. AI leaves blank. |
| Key Takeaways | AI drafts one-liners; asks you to confirm before finalising |
| Index file | AI outputs one row for `_index.md` at end of every session |

> **Primary focus in every phase: code, design decisions, architecture decisions, tradeoffs.**
> Conceptual explanation is support material — not the main event.

---

## AI Behaviour Instructions
*(Copy and paste this block at the start of every journal session)*

```
You are helping me maintain a learning journal for agentic AI / agent engineering.

Rules you must follow without exception:

1. APPEND vs FRESH
   - If today's entry already has content → append the next Phase block.
     Phase numbers restart at 1 each day. The date is the outer key.
   - If no entry exists for today → start from Business / Problem Statement.
   - If I say I'm tired or short on time → use the Quick Entry format instead.
     Ask me at the end: "Want to promote this to a full entry?"

2. PARTIAL TEMPLATE
   - If I paste a template that is already partially filled → scan what is present.
   - Ask me: "I can see sections X and Y are filled. Should I complete the missing
     sections, or are you only updating specific parts?"
   - Wait for my answer before writing anything.

3. SESSION METADATA
   - Always open a new day's entry by asking:
       • How long did this session run?
       • What resource are you learning from? (docs, course, paper, video — title + URL)
       • What framework/library version are you using?

4. TL;DR — FILL LAST, PLACE FIRST
   - After all phases are done, ask: "Ready to write the TL;DR?"
   - Draft 3 bullet points max. I confirm before placing.
   - It goes directly under Session Metadata, before Phase 1.

5. DESIGN DECISIONS
   - For every phase, ask: "Was there an alternative you considered, even briefly?"
   - If yes → include the Design / Architecture Decision block.
   - Never skip this question.

6. DEFERRED DECISIONS
   - After the Design Decision block (or where it would be), ask:
       "Was there anything you consciously chose not to decide yet? Why?"
   - If yes → include the Deferred Decision block.
   - A deliberate "not yet" is as important as a made decision.

7. MISTAKES SECTION
   - Never write anything in the Mistakes section on your own.
   - Ask these four questions for the FIRST mistake:
       Q1: What was the first thing you tried that didn't work? (paste code or describe)
       Q2: Why did it seem like the right move at the time?
       Q3: What was the actual error or failure signal? (traceback, wrong output, symptom)
       Q4: What was the fix? (paste corrected code or describe the change)
   - After recording the first mistake, ask: "Was there another wrong turn before the fix?"
   - If yes → repeat the four-question cycle as Mistake 2, Mistake 3, etc.
   - If nothing broke: write > No mistake recorded for this phase.

8. PREDICTION VS REALITY
   - After writing up each phase, ask:
       "Before you ran this — what did you expect? And what actually happened?"
   - Gap found → capture it. Matched → skip the block.

9. CONFIDENCE RATING
   - After each phase, ask: "How confident are you in this concept? (1 = shaky, 5 = solid)"
   - Record in the phase header.
   - If ≤ 2, follow up: "What specifically feels shaky?"
     Capture as a sub-note. This becomes a targeted open question.

10. CONTINUITY LINKS
    - For each phase, ask: "Does this build on or contradict anything from a previous entry?"
    - If yes → add a Builds On block: filename + phase reference + what it extends.
    - At end of session, ask: "Are any open questions from previous entries resolved now?"
      If yes → ✅ Resolved (YYYY-MM-DD): <how it was answered>

11. FORMAT
    - Use whichever format best serves the concept: prose, table, diagram, ASCII flow, or code.
    - Do NOT default everything to code blocks.
    - Primary emphasis: code, design decisions, architecture decisions, tradeoffs.

12. OPEN QUESTIONS & NEXT EXPERIMENTS
    - Leave as empty checkboxes. Do not generate content.
    - At end of session remind me: "Don't forget Open Questions and Next Experiments."

13. CARRY-FORWARD
    - Pasted open questions from previous entries:
      → Resolved: prefix with ✅ Resolved (YYYY-MM-DD): <how answered>
      → Unresolved: leave as-is with original date

14. SESSION RETROSPECTIVE
    - At the very end, after Key Takeaways, ask exactly this one question:
        "If you were starting this notebook today with what you know now,
         what would you do differently?"
    - Record the answer in the Session Retrospective block.
    - This is the last thing written before the index row.

15. KEY TAKEAWAYS
    - Draft one-liners per concept, ask me to confirm or edit before finalising.

16. INDEX ROW
    - At the end of every session, output this row for _index.md:
      | YYYY-MM-DD | <notebook.ipynb> | <topic> | <one-line TL;DR> | <shaky concepts or —> |
    - Say: "Append this row to your _index.md file."

17. ARCHITECT CAPTURE (end goal: architect)
    - Ask: "What hard constraint was this built against?" Record it in Session Metadata.
    - If a real design fork happened (≥2 viable options under a constraint), say:
      "This looks like an architecture decision — record it with /adr so it lands in the Design Decisions Log."
    - If an ADR exists, prompt: "Run /adr reconcile <NNNN> to fill predicted-vs-actual failure modes."
```

---

# Journal Entry — YYYY-MM-DD

## Session Metadata

| Field | Value |
|---|---|
| Duration | <e.g. 1h 30m> |
| Resource | <title + URL or citation> |
| Framework / Version | <e.g. LangGraph 0.2.x, Python 3.11> |
| Notebook | `<filename.ipynb>` |
| Constraint(s) designed against | <hard constraint, e.g. ≤ $0.01/query & p95 < 2s — or "none this session"> |
| ADR(s) | `decisions/NNNN-*.md` if a design fork was recorded — else — |

---

## TL;DR
*(Written last, placed here — 3 bullets max. AI drafts, you confirm.)*

-
-
-

---

## Business / Problem Statement
*(First entry for this notebook only — skip on append)*

<!-- 2–3 sentences: what is broken or suboptimal in the naive approach? Why does it matter? -->

**The Solution: `<Name>`**

<!-- 1–2 sentences: what is the fix and why does it work structurally? -->

**The workflow built in this notebook:**
1. **`<Role 1>`** — <what it does>
2. **`<Role 2>`** — <what it does>
3. **`<Role 3>`** — <what it does>

---

## Phase 1 — `<Title>`
*Confidence: ?/5*
<!-- If ≤ 2, add: *Shaky on: <what specifically feels unclear>* -->

> **Iteration:** <one-line summary of what this phase establishes>

<!-- Context: why does this phase exist? What problem does it solve? -->

### Builds On
*(skip if standalone)*

> `<previous_entry_filename.md>` → Phase <N> — <what this phase extends or depends on>

---

### Design / Architecture Decision
*(skip if no real choice was made)*

> **Architect note:** if this was a real fork (≥2 viable options chosen under a constraint), record it as an ADR via `/adr` and link it in Session Metadata. Include a decision matrix across the candidates, not just one rejected alternative.

**Alternative considered — `<approach>`**

<!-- Code, table, diagram, or prose — whichever is clearest -->

**Why it was rejected:** <concrete reason>

---

**Chosen approach — `<approach>`** ✓

<!-- Code, table, diagram, or prose -->

**Why this wins:**

| Concern | Tradeoff |
|---|---|
| `<concern>` | <why the chosen approach handles it better> |

**The principle:** <one generalizable rule from this decision>

---

### Deferred Decision
*(skip if nothing was consciously left undecided)*

> **What was not decided:** <describe the open choice>
> **Why deferred:** <not enough data / too early / dependency on something else>
> **Trigger to revisit:** <what would need to be true before making this call>

---

### Implementation

<!-- Format guide — pick what fits, combine freely:
     • Code block     → executable logic, state shape, node wiring
     • Table          → field definitions, comparisons, input/output shapes
     • Prose          → mental models, causality chains, analogies
     • ASCII/diagram  → flows, topologies, fan-out/fan-in, execution timelines -->

```python
# paste actual cell code here
```

**Input:**

| Field | Type | Value / Description |
|---|---|---|
| `<field>` | `<type>` | <description> |

**Output:**

```python
# actual or representative output
```

| Field | Purpose | Used By |
|---|---|---|
| `<field>` | <purpose> | <downstream node or consumer> |

---

### Prediction vs Reality
*(skip if expectations matched reality exactly)*

> **Expected:** <what you thought would happen>
> **Actual:** <what really happened>
> **Why the gap existed:** <mental model that was off>

---

### Failure Modes — Predicted vs Actual
*(skip if no ADR / no design fork this phase)*

> **Predicted (from the ADR):** <where you expected it to break + detection signal>
> **Actual:** <what actually broke, or didn't>
> **Accuracy:** <which predictions held> → reconcile with `/adr reconcile <NNNN>`

---

### Mistakes
*(AI runs the four-question cycle once per mistake — repeat the block for each one)*

**Mistake 1**

> **Mistake:** <what went wrong>
> **Why tempting:** <why it seemed right>
> **Fix:** <what changed>

**Mistake 2** *(if applicable)*

> **Mistake:** <what went wrong>
> **Why tempting:** <why it seemed right>
> **Fix:** <what changed>

<!-- Add Mistake 3, 4... as needed. If nothing broke: -->
<!-- > No mistake recorded for this phase. -->

---

## Phase 2 — `<Title>`
*Confidence: ?/5*

*(repeat Phase structure above)*

---

## Open Questions
*(You fill this — AI leaves blank, reminds you at end of session)*

Unresolved items become next session's agenda. Carry forward with originating date.

- [ ] *(YYYY-MM-DD)*
- [ ] *(YYYY-MM-DD)*
- [ ] *(YYYY-MM-DD)*

**Resolved this session:**

- ✅ Resolved (YYYY-MM-DD): <original question> → <how it was answered>

---

## Next Experiments
*(You fill this — AI leaves blank)*

Format: **verb + what + what to measure.**

- [ ]
- [ ]
- [ ]

---

## Key Takeaways Summary
*(AI drafts one-liners, you confirm or edit before finalised)*

| Concept | One-liner |
|---|---|
| `<concept>` | <takeaway> |
| `<concept>` | <takeaway> |
| `<concept>` | <takeaway> |

---

## Session Retrospective
*(AI asks one question at the very end: "If you were starting this notebook today with what you know now, what would you do differently?")*

>

---
---

# Quick Entry — YYYY-MM-DD
*(Tired, short on time, or capturing one thing. Under 2 minutes. Promote to full entry later.)*

**What I did:**

**The one thing worth remembering:**

**Anything broken or confusing?** *(optional — paste error or describe)*

**Promote to full entry later?**
- [ ] Yes

---
---

# _index.md — Master Index
*(One file at the root of your journal folder. AI outputs one row per session — you paste it in.)*

## How to use
- Keep this file at the top level of your journal folder.
- After each session the AI outputs a table row. Paste it here.
- Use it to find entries fast, spot patterns in shaky concepts, and see your learning arc over time.

## Index

| Date | Notebook | Topic | TL;DR | Shaky Concepts |
|---|---|---|---|---|
| YYYY-MM-DD | `<notebook.ipynb>` | <topic> | <one-line summary> | <concept if confidence ≤ 2, else —> |
