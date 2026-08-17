---
name: session-prep
description: Pre-session warm-up ritual. Surfaces the last session's core insight, all open questions, shaky concepts, and a concrete focus recommendation. Run at the start of every learning session instead of re-reading journals manually.
disable-model-invocation: true
---

The user is starting a learning session. Arguments: $ARGUMENTS

## Purpose

Eliminate the 5–10 minutes of re-reading journals at session start. Load the learning context into working memory in under 2 minutes, and give a concrete recommendation for what to focus on today.

## Instructions

### 1. Determine target

Parse $ARGUMENTS:
- Module name (e.g., `hierarchical_agent_teams`) → prep for that module
- `next` or empty → infer the most productive next step from `_index.md` and roadmap
- `open-questions` → focus entirely on surfacing and prioritizing open questions

### 2. Read all relevant state

Read in parallel:
- `_index.md` — full learning arc, shaky concepts, open questions table
- `LEARNING_ROADMAP.md` — which phase is current, what's next in the series
- `<target_module>/learning.md` — the most recent session entry
- If `next` mode: also read the last 2–3 modules' `learning.md` for context
- `decisions/*.md` (if present) — open ADRs, and any with predicted-but-no-actual failure modes (follow-up debt)

### 3. Output: Session Context Brief

Format this as a structured brief — scannable in 90 seconds.

---

```
## Session Context — <today's date>

### Last Session Recap
**Module:** <module>  **Date:** <date>
**Core insight:** <the TL;DR from last session's learning.md — one sentence>
**What was built:** <2-sentence summary of the system/pattern implemented>

### Open Questions (still unresolved)
N questions outstanding — ranked by relevance to today's planned work:
1. [Question] — raised <date>, module: <module>
2. ...

### Shaky Concepts
<Any concept ≤ 2/5 confidence from _index.md or flagged in learning.md>
- <concept>: <brief description of what felt uncertain>
Recommendation: /explain-deep <concept> before building new code

### Concept Continuity
Today's work builds on:
- <previous pillar> → <how it connects to today's module>
The pattern to watch for: <the fan-out/fan-in variation in today's pillar>

### Architect Check
- Build project or new pattern today? If yes and no ADR exists → run /adr <title> *before* coding.
- Open ADRs awaiting reconciliation: <list NNNN with predicted-but-no-actual, or "none">
- One pattern to push from "can build" → "can choose": <name a D1→D2 candidate>

### Recommended Focus for This Session
Given your learning arc, focus on:
1. **[Primary]** <specific concept or experiment — be concrete>
2. **[Secondary]** <one open question to try to answer through experimentation>

Avoid: Starting with X until Y is clearer (if applicable).

### Quick LangGraph Reminders
(Only show if relevant to today's module)
- Manual tool loop: `prompt | llm_with_tool` returns AIMessage — invoke tools yourself
- State init: Guard with `state.get("field", default)` — fields don't exist until populated
- Free-tier API: Add `max_concurrency=1` to `.batch()` calls before running
```

---

### 4. If mode is `next` — recommend what to work on

Read `LEARNING_ROADMAP.md` and the learning arc. Suggest:

```
### What to Work On Next

Based on 6 sessions and the roadmap:
- You've completed: [list of pillars done]
- Next recommended pillar: <name> (Phase N in roadmap)
- Why now: <1-2 sentence rationale connecting current mastery to next concept>
- Prerequisite check: Before starting, make sure [concept X] is solid — run /concept-check <X> if uncertain

To scaffold the new module: run /new-module <name>
```

### 5. Estimated session time

End with:
```
**Estimated productive session:** <N> hours
(Based on: complexity of next topic + N open questions to potentially resolve)
```
