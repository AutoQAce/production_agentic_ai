---
name: notebook-debug
description: LangGraph/LangChain-specific debugging for notebook cell errors. Matches errors against known project gotchas, explains the root cause, and provides a targeted fix. Faster than reading docs from scratch.
disable-model-invocation: true
---

The user has a notebook error. Arguments: $ARGUMENTS

## Purpose

Reduce time-to-fix for the most common LangGraph/LangChain error patterns in this project. The errors documented in the learning journals are the gold standard — check there first before generic debugging.

## Instructions

### 1. Collect the error

Parse $ARGUMENTS for an error message, traceback, or description. If none provided, ask:
"Paste the full traceback or describe what the cell outputs."

Also ask (if not obvious from the traceback):
- Which module/notebook is this in?
- Which cell number (approximately)?
- What were you trying to do?

### 2. Check the known-gotchas database

Read `_index.md` and all `learning.md` files to check for documented mistakes matching this error.

**Priority match list (from this project's journals):**

| Error pattern | Root cause | Fix |
|---|---|---|
| `KeyError: '<field>'` in a graph node | TypedDict field read before initialization | Guard with `state.get("field", default)` or ensure the input dict populates it |
| Graph runs but tool results are missing | Assumed `prompt \| llm_with_tool` auto-executes tools | Manually extract `tool_calls` from AIMessage, invoke each tool, wrap in `ToolMessage`, re-invoke LLM |
| `429 Too Many Requests` from API | Parallel branches hitting free-tier rate limit | Add `max_concurrency=1` to `.batch()` call |
| Output from parallel branches overwrites silently | State field not declared with `Annotated[Type, reducer]` | Declare as `Annotated[list[T], operator.add]` (or appropriate reducer) |
| Judge/synthesizer node takes 10x longer than workers | Expected: workers do parallel I/O; judge does sequential reasoning | Not a bug — judge is running a full LLM reasoning pass; workers just call APIs |
| `AttributeError` on `tool_calls` | AIMessage has no `tool_calls` because LLM didn't call a tool | Check that the tool is properly bound: use `llm.bind_tools([tool])` not `llm.bind(tools=[tool])` |
| Graph never terminates | Conditional edge always routes back to the same node | Check the condition function — it may be returning the wrong node name string |
| `TypeError: unhashable type` in graph state | Mutable default in TypedDict (e.g., `field: list = []`) | Use `field: Annotated[list, operator.add]` or initialize via input dict only |
| `ValidationError` from Pydantic | LLM output doesn't match the Pydantic schema | Check the `.with_structured_output(Model)` call; use `method="json_mode"` if schema is complex |
| `Future` result `.result()` hangs forever | Tool raised an exception without propagating it | Wrap tool call in try/except and call `future.exception()` to inspect |
| Import errors for `langchain_community` | Package not installed or wrong namespace | Run `uv add langchain-community`; community tools may have moved namespaces |
| LangSmith not tracing | `.env` not loaded before import | Call `load_dotenv()` before any `langchain` import |

### 3. Diagnose

Match the user's error against the table above. If it matches:

```
**Root cause identified:** <error pattern label>

**Why this happens:** <2-3 sentence mechanism explanation — not just "the docs say so" but the actual Python/LangGraph reason>

**Fix:**
```python
# Before (broken)
<broken code snippet>

# After (fixed)
<fixed code snippet>
```

**Verification:** After applying the fix, run the cell again. You should see: <expected output>
```

If it doesn't match the known patterns:

```
**Not a known pattern.** Let's diagnose:

1. <First diagnostic step — specific to this error type>
2. <Second diagnostic step>
3. <Third diagnostic step>

Paste the output after step 1 and we'll narrow it down.
```

### 4. Also check the CLAUDE.md patterns

Before concluding, verify against the project-specific runtime patterns in CLAUDE.md:

- Is this a **manual tool invocation** issue? (`prompt | llm_with_tool` doesn't invoke tools)
- Is this a **state field initialization** issue? (TypedDict fields don't exist until populated)
- Is this a **rate limiting** issue? (free-tier APIs need `max_concurrency=1`)
- Is this a **parallel reducer** issue? (missing `Annotated[Type, reducer]` for merged fields)

### 5. Suggest a learning.md entry

If this was a genuinely new bug not already documented:

```
**Worth documenting:** This is a pattern not yet in your learning journals.
Add to <module>/learning.md under "Mistakes / Gotchas":
> If you [X], [Y] happens. Fix: [Z].

Run /update-learning <module> to capture this session.
```
