---
name: pattern-map
description: Cross-pillar pattern synthesis. Reads all learning journals and notebooks to show how the same primitives (ThreadPoolExecutor, Send, Annotated, etc.) appear at different abstraction levels across pillars. Builds the mental model that every pillar is fan-out/fan-in applied to a different layer.
disable-model-invocation: true
---

The user wants a cross-pillar pattern map. Arguments: $ARGUMENTS

## Purpose

The breakthrough insight in this project is that every pillar uses the same fan-out/fan-in primitive at a different layer of the agent stack. This skill makes that explicit — turning 6 separate notebooks into one unified mental model.

## Instructions

### 1. Determine scope

Parse $ARGUMENTS:
- Empty or `all` → full cross-pillar synthesis across all completed modules
- Primitive name (e.g., `ThreadPoolExecutor`, `Annotated`, `Send`) → trace that primitive across all pillars
- Pattern name (e.g., `map-reduce`, `fan-out`, `manual tool loop`) → find all instances of this pattern
- Module name → compare that module's patterns against all others

### 2. Read all available state

Read ALL of these before producing any output:
- `_index.md` — learning arc summary
- Every `<module>/learning.md` that exists
- `LEARNING_ROADMAP.md` — for upcoming pillars to predict where patterns will appear next

### 3. Build the pattern map

#### 3a. The Primitive Inventory

For each primitive/mechanism that appears across multiple pillars, create a row:

```
## Primitive Inventory

| Primitive | Pillars where it appears | What it does in each context |
|---|---|---|
| `ThreadPoolExecutor` | parallel_tool_use, hierarchical_agent_teams | parallel_tool_use: runs tool calls in parallel inside ToolNode; hierarchical: workers run in parallel inside `.batch()` |
| `Annotated[Type, reducer]` | speculative_execution, hypothesis_generation | speculative: merges Future results from parallel branches; hypothesis: merges worker outputs before judge |
| `Send()` API | hypothesis_generation | fan-out: dispatches independent hypothesis workers with individual payloads |
| `operator.add` | parallel_tool_use, hypothesis_generation | accumulates list outputs from parallel branches (message history, hypothesis list) |
| `max_concurrency` | parallel_evaluation | rate-limits parallel execution without changing graph structure |
| `Pydantic model` as contract | parallel_evaluation, hierarchical_agent_teams | defines the typed interface between agents; prevents untyped dict passing |
| Manual tool loop | hierarchical_agent_teams | extracts tool calls from AIMessage, invokes tools, builds ToolMessages, re-invokes LLM |
| `state.get(field, default)` | hierarchical_agent_teams | guards against KeyError on uninitialized TypedDict fields |
```

Populate from the actual learning journals — only include entries for pillars that have been completed.

#### 3b. The Abstraction Layer Map

Show where fan-out/fan-in is applied in each pillar:

```
## Fan-Out / Fan-In by Layer

The same pattern, applied at progressively higher abstraction levels:

Layer 1 — Tool execution (parallel_tool_use)
  Fan out:  ToolNode fans out over N tool calls in one AIMessage
  Fan in:   N ToolMessages collected back into state.messages
  Primitive: ThreadPoolExecutor inside ToolNode (hidden from user code)

Layer 2 — Idea generation (hypothesis_generation)
  Fan out:  Send() fans out N independent hypothesis workers
  Fan in:   Annotated[list, operator.add] accumulates worker outputs
  Primitive: Send() + Annotated reducer (user-controlled)

Layer 3 — Evaluation (parallel_evaluation)
  Fan out:  N critic agents evaluate the same content simultaneously
  Fan in:   Chief Editor synthesizes N Critique objects into FinalDecision
  Primitive: .batch() with max_concurrency config + Pydantic contracts

Layer 4 — Execution timing (speculative_execution)
  Fan out:  Fire tool Futures before LLM finishes deciding
  Fan in:   Annotated reducer merges pre-fetched results with decided path
  Primitive: concurrent.futures.Future + Annotated reducer

Layer 5 — Role specialization (hierarchical_agent_teams)
  Fan out:  Specialist workers (financial, news) run in parallel
  Fan in:   Synthesizer merges typed outputs into final response
  Primitive: parallel .batch() + Pydantic typed contracts between workers/synthesizer
```

#### 3c. The Concept Dependency Graph

Show which concepts must be understood before others:

```
## Concept Dependencies

ThreadPoolExecutor (I/O parallelism basics)
    └── ToolNode internals
        └── batch() for multiple states
            └── max_concurrency for rate limiting

TypedDict + GraphState basics
    └── state field initialization (KeyError gotcha)
        └── Annotated[Type, reducer] for parallel merge
            └── Send() for dynamic fan-out
                └── Future-based speculative execution

LLM tool binding (bind_tools)
    └── AIMessage.tool_calls parsing
        └── Manual tool loop (ToolMessage construction)
            └── Hierarchical agent coordination

Pydantic models (basic)
    └── Pydantic as agent contract
        └── Structured output from LLM (.with_structured_output)
            └── Multi-critic typed evaluation pipeline
```

Mark any node in the graph where a mistake was documented in the journals — these are the actual learning moments.

### 4. Surface the meta-pattern

After the maps, state the synthesis explicitly:

```
## The Meta-Pattern

Every agentic AI pillar in this series is the same idea at a different scale:
SPLIT → PROCESS IN PARALLEL → MERGE

The split mechanism changes: ToolNode / Send() / batch() / Future
The merge mechanism changes: messages list / Annotated reducer / Pydantic synthesizer
The abstraction level changes: sub-LLM / LLM call / multi-LLM team

The primitives that repeat: ThreadPoolExecutor, Annotated, operator.add, Pydantic contracts

This means: once you understand the pattern at one layer, you can predict how it will appear at the next layer. The upcoming pillars (Phase 2–6 in roadmap) will apply this pattern to: RAG retrieval, memory management, evaluation pipelines, and multi-agent coordination.
```

### 5. Predict upcoming patterns

Based on `LEARNING_ROADMAP.md` Phase 2+ articles, predict where these primitives will appear next:

```
## Pattern Predictions for Upcoming Phases

Phase 2 (RAG Core):
- Same fan-out pattern, but for document retrieval: retrieve from N sources → merge results
- Pydantic contracts will reappear as retrieval + generation interfaces

Phase 3 (Memory):
- Annotated reducer pattern for memory accumulation (append-only vs. replace)
- New primitive: checkpointing (InMemorySaver → actual persistent store)

Phase 4 (Evaluation):
- Already seen in parallel_evaluation — this phase formalizes it with LangSmith metrics
...
```
