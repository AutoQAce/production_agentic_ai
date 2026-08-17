---
name: quick-recap
description: 3-minute spaced repetition recap of any module. Distills a learning journal down to the core insight, key gotchas, and the one pattern to remember. Use the day after a session to cement retention.
disable-model-invocation: true
---

The user wants a fast recap. Arguments: $ARGUMENTS

## Purpose

Spaced repetition requires retrieval at increasing intervals: next day, 3 days later, 1 week, 1 month. This skill produces a 3-minute read — dense enough to re-activate memory, short enough to actually do it.

## Instructions

### 1. Identify target

Parse $ARGUMENTS:
- Module name → recap that module
- `yesterday` or empty → find the most recent session in `_index.md` and recap it
- `all` → produce a one-liner recap per module (the full arc view)

### 2. Read the journal

Read `<module>/learning.md`. Focus on:
- The most recent session entry
- TL;DR and Key Takeaways sections
- Mistakes / Gotchas section
- Open Questions (unresolved checkboxes)

### 3. Output: The Recap Card

Format as a dense, scannable card — **no padding, no preamble**.

---

```
## Quick Recap — <Module Name>
**Session:** <date> | **Confidence:** <N/5 from journal, or "not rated">

### The Core Insight
<One sentence. The single most important thing from this session.>

### What Was Built
<One sentence describing the system/pattern — specific enough to trigger visual memory of the code.>

### The Pattern
<The abstract pattern this pillar demonstrates — where it sits in the fan-out/fan-in meta-pattern.>

### 3 Gotchas to Remember
1. **<Short label>:** <If you do X, Y happens. Fix: Z.>
2. **<Short label>:** <If you do X, Y happens. Fix: Z.>
3. **<Short label>:** <If you do X, Y happens. Fix: Z.>

### Open Questions (still unresolved)
- [ ] <question>
- (or "None — all questions resolved")

### Next Time You See This Pattern
<One sentence trigger: "When you see [X], remember [Y].">
```

---

### 4. If mode is `all` — full arc view

Produce one line per module, showing the learning arc:

```
## Learning Arc Recap — All Modules

| Date | Module | Core Insight | Confidence |
|------|--------|-------------|------------|
| 2026-05-16 | Parallel Tool Use | ToolNode runs tools in parallel internally — batch() is for multiple states | 5/5 |
| ...  | ...    | ...         | ...        |

**Meta-pattern:** Every pillar applies fan-out/fan-in at a different layer.
**Shaky spots:** <any concept ≤ 3/5 from the table>

Run /concept-check all to test synthesis across all pillars.
```

### 5. End with a retrieval prompt

After showing the card, ask one question to force active retrieval:

```
**Quick retrieval test:** Without scrolling up — what is the ONE thing from this session you'd tell a teammate who is about to implement this pattern for the first time?
```

This is not graded. It's a memory activation. If they struggle, suggest `/explain-deep <concept>` for the specific part that didn't come up.
