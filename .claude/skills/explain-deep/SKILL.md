---
name: explain-deep
description: Feynman-technique deep explanation of any LangGraph, LangChain, or agentic AI concept. Six progressive layers — definition, problem, mechanism, mental model, gotchas, limits — grounded in the project's own notebooks.
disable-model-invocation: true
---

The user wants a deep explanation of a concept. Arguments: $ARGUMENTS

## Purpose

When a concept feels slippery or abstract, crystallize it into a durable mental model. The Feynman rule: if you can't explain it simply, you don't understand it yet. This skill forces that simplicity, then progressively deepens it.

## Instructions

### 1. Identify the concept

Parse $ARGUMENTS. Accept any of:

**LangGraph/LangChain primitives:**
`Annotated`, `Send`, `ToolNode`, `batch`, `ThreadPoolExecutor`, `TypedDict`, `Runnable`, `RunnableLambda`, `AIMessage`, `ToolMessage`, `HumanMessage`, `add_messages`, `operator.add`, `InMemorySaver`, `StateGraph`, `CompiledGraph`, `create_react_agent`, `langgraph_supervisor`

**Patterns from this project:**
`fan-out/fan-in`, `map-reduce`, `manual tool loop`, `state initialization`, `parallel evaluation`, `speculative execution`, `hierarchical agents`, `hypothesis generation`, `multi-critic panel`, `structured output`, `Pydantic contract`

**Generic agentic AI concepts:**
`LLM tool calling`, `ReAct loop`, `chain of thought`, `context window management`, `rate limiting`, `concurrency`, `reducer`, `graph state`, `node`, `edge`, `conditional edge`

If $ARGUMENTS is empty, ask: "Which concept do you want to dig into?"

### 2. Before explaining — check the journals

Read:
- `_index.md` — has this concept been marked shaky or raised as an open question?
- Any `learning.md` that mentions this concept — what mistakes did you already make with it?

Surface any documented confusion at the start: "You've noted this concept as shaky before — specifically around [X]. I'll pay extra attention to that."

### 3. Explain in 6 layers

Present these layers in order. Each layer must be concrete, not abstract.

---

**Layer 1 — One-sentence definition**
What it IS. No jargon beyond what's needed. Aimed at someone who has never seen it.

Example: "`batch()` runs the same Runnable against N different inputs, returning N outputs."

---

**Layer 2 — The problem it solves**
What breaks WITHOUT it. Show the failure mode before showing the solution.

Example: "Without `Annotated[Type, reducer]`, two parallel branches writing to the same GraphState field would overwrite each other silently — last write wins, losing the other branch's output."

---

**Layer 3 — Mechanism (how it works under the hood)**
The actual Python/LangGraph execution path. What objects are created, what methods are called, what the internals actually do.

For LangGraph concepts: trace which method on which class does the work.
For concurrency concepts: name the thread/process model.
For Pydantic concepts: show the validation moment.

Example for `ToolNode.invoke()`:
"When `ToolNode.invoke(state)` is called, it reads the `messages` list from state, finds any `AIMessage` entries whose `tool_calls` list is non-empty, and for each tool call, spawns a thread via `ThreadPoolExecutor.submit()` — running each tool function in parallel. It collects the results and wraps each in a `ToolMessage`, appending them to the state."

---

**Layer 4 — Mental model (the analogy)**
One analogy that makes it stick. Choose a physical-world process that mirrors the data flow.

Criteria for a good analogy: it should predict the behavior correctly, not just label it.

Examples:
- `batch()`: "Like sending 5 letters in one trip to the post office vs 5 separate trips. The letters are processed independently but the trip overhead is paid once."
- `Annotated[Type, reducer]`: "Like a ballot box — each parallel branch drops in a vote (partial result), and the reducer is the vote counter that merges them all into one result at the end."
- Manual tool loop: "Like a relay race. The baton (ToolMessage) must physically pass through your code before the next runner (LLM call) can move."
- `Send()` API: "Like firing named rockets at specific graph nodes — you address each rocket to a node and it carries its payload directly there, bypassing the main control flow."

---

**Layer 5 — Gotchas and misconceptions**
What people get wrong. Framed as "You might think X, but actually Y."

Prioritize:
1. Mistakes documented in the project's learning journals
2. Common LangGraph beginner errors
3. Python concurrency pitfalls

Examples:
- "You might think `prompt | llm_with_tool` executes the tools. It doesn't — it returns an `AIMessage` with `tool_calls` metadata. You must extract the calls, invoke each tool, wrap in `ToolMessage`, and re-invoke the LLM."
- "You might think TypedDict fields exist at runtime. They don't — TypedDict is purely a type annotation. Reading a field that was never assigned raises `KeyError`."
- "You might think `max_concurrency=1` serializes only the `.batch()` call. It actually applies to the graph's internal parallel execution too, serializing ALL node invocations."

---

**Layer 6 — When NOT to use it**
The boundary. What problem this concept is NOT suited for.

Example: "`ThreadPoolExecutor` (used internally by `ToolNode` and `batch()`) is for I/O-bound parallelism. CPU-bound work (heavy computation, model inference) needs `ProcessPoolExecutor` to bypass Python's GIL, otherwise threads compete and performance can be worse than sequential."

---

### 4. Tie it to this project

After the 6 layers, show:

```
**In this codebase:**
- <module>: used here for [specific purpose] — see cell N in <notebook>.ipynb
- Contrast: <other module> uses [related concept] differently because [reason]
```

### 5. Confidence check

End with:

```
**Your turn:** Explain [concept] back to me in 2 sentences without scrolling up.
```

Wait for the user's answer. If it captures the core mechanism: "Good — that's the mental model to keep." If it misses: "What part of the mechanism is fuzzy?" Then re-explain only that layer, more concretely.
