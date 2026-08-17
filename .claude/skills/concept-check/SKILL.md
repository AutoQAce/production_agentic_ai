---
name: concept-check
description: Socratic quiz to test understanding of concepts from the learning journals. Generates targeted questions at three cognitive levels (recall, application, synthesis), evaluates answers, and flags gaps for spaced repetition.
disable-model-invocation: true
---

The user wants a concept quiz. Arguments: $ARGUMENTS

## Purpose

Transform passive learning into active retrieval. Spaced repetition works only if retrieval is effortful — these questions are designed to be hard enough to feel uncomfortable but fair enough to be answerable from what's been learned.

## Instructions

### 1. Determine scope

Parse $ARGUMENTS:
- Module name (e.g., `parallel_tool_use`, `hierarchical_agent_teams`) → quiz that module only
- `all` or empty → quiz across all modules, require synthesis answers
- Concept name (e.g., `Send API`, `Annotated`, `ToolNode`, `batch`) → drill that one concept deep

### 2. Read the learning state

Read these files before generating any question:
- `_index.md` — for the full learning arc, shaky concepts, and open questions
- `<module>/learning.md` for each relevant module — for concepts covered, mistakes made, gotchas documented
- `concepts_learning_template.md` — to understand what sections contain design decisions vs mistakes

### 3. Generate the quiz

Produce **5 questions** for a single-module quiz or **8 questions** for an all-modules review.

Mix three levels in every quiz:

**Level 1 — Recall (2 questions):** Test that the fact is retrievable.
Examples:
- "What does `ToolNode.invoke(state)` actually return — and what does it NOT do?"
- "What happens when you read a TypedDict field that has never been assigned a value?"
- "What does `max_concurrency=1` do to a parallel LangGraph graph?"

**Level 2 — Application (2–3 questions):** Test that the concept can be applied to a scenario.
Examples:
- "Your free-tier API is throwing 429 errors on a parallel graph. What is the single config change to fix it without touching any node code?"
- "You want two parallel branches to each contribute items to a list in GraphState. Write the state field declaration (one line of Python)."
- "Describe the exact sequence of objects that must be built and passed after `llm_with_tool` returns — before the LLM can be called again."

**Level 3 — Synthesis (1–2 questions):** Test cross-pillar understanding.
Examples:
- "Every pillar so far uses fan-out/fan-in. Name 3 pillars and state what is being fanned out in each case."
- "When would you use `Send()` vs `Annotated[Type, reducer]` to parallelize a graph? What is the difference in what problem each solves?"
- "The judge node in hypothesis generation takes 22s while workers take 0.7s. What are two likely explanations?"

Pull from documented mistakes and open questions in the learning journals — these make the best questions because they represent real confusion points.

### 4. Ask questions one at a time

Present ONE question. Wait for the user's answer. Then present the next.

Format each question as:
```
**Question N of N — [Recall / Application / Synthesis]**

<question text>

> Think it through before answering.
```

### 5. Evaluate each answer

After the user responds:

- **Correct:** "Yes — [one-line reinforcement of the exact mechanism, not just confirmation]"
- **Partially correct:** Identify what's right first. Then: "The part to add: [specific gap]"
- **Incorrect:** Do NOT immediately give the answer. Ask a Socratic follow-up that scaffolds toward the correct answer: "What type does `ToolNode.invoke()` return according to LangChain's Runnable protocol?"

Always end evaluation with the **canonical one-liner** — the exact phrasing to carry forward in memory.

Mark any answer that reveals a genuine misconception with: `[Gap flagged — add to review]`

### 6. Final score and recommended action

After all questions:

```
**Quiz Result — N/N**

Strong: <list concepts answered correctly>
Gaps:   <list concepts answered incorrectly or partially>

Recommended action:
- /explain-deep <concept> for each gap
- /quick-recap <module> to re-read the relevant journal section
- Next experiment: <one concrete thing to run in a notebook to cement the shakiest concept>
```

If the score is ≤ 60%: recommend running `/session-prep` before the next coding session rather than pushing forward.

If any open question from `_index.md` was surfaced by an answer: flag it as "still open" and note which journal entry raised it.
