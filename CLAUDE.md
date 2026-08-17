# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

This is a Jupyter notebook-based learning project for **Article #30, Phase 9 (Production Infrastructure & Scale)** of the agent engineering curriculum:
**"Building the 7 Layers of a Production-Grade Agentic AI System"** (Fareed Khan / Level Up Coding).

> **Two-stage article:** it is also the **Production Lens** early-read (right after Phase 1) — read conceptually to distill `production_readiness_checklist.md` (done 2026-07-19). The **hands-on build stays here in Phase 9**.

**Phase 9 theme:** Production Infrastructure & Scale — serving, layered architecture, fault handling, and observability. Read early as a structural mental model of how production agentic systems are layered, before building complex components.

**What this article covers:**
- The 7 architectural layers that make up a production-grade agentic AI system
- How each layer (perception, memory, reasoning, planning, action, monitoring, orchestration) interacts
- Design patterns and trade-offs at each layer
- How these layers map onto real LangGraph / LangSmith implementations

Each top-level directory is a self-contained module covering one or more layers (e.g., `perception_layer/`, `memory_layer/`, `orchestration_layer/`). Each module contains a `.ipynb` notebook and a `learning.md` journal.

**Architect track constraint (Phase 1):** The diagram must show ≥2 rejected alternatives per major component, each with the reason.

## Package Manager: uv

This project uses `uv`, not `pip` or `poetry`.

```bash
uv sync                  # install/update all dependencies from uv.lock
uv add <package>         # add a new dependency
uv remove <package>      # remove a dependency
uv run python <script>   # run a script in the project virtualenv
```

Never use `pip install` directly — it bypasses the lockfile.

## Linting and Type Checking

```bash
uv run ruff check .      # lint
uv run ruff format .     # format
uv run mypy .            # type check
```

**Ruff config** (from `pyproject.toml`):
- Google docstring convention (`D` rules, `pydocstyle.convention = "google"`)
- Line length is **not** enforced (E501 ignored)
- Modern type syntax enforced (`UP` rules) — use `list[str]` not `List[str]`, `str | None` not `Optional[str]`
- `UP006`, `UP007`, `UP035`, `D417` are ignored
- Test files are exempt from docstring requirements

## LangGraph Runtime Patterns

**Manual tool invocation loop:** `prompt | llm_with_tool` returns an `AIMessage` with tool call metadata — it does NOT invoke the tool. The loop (extract → invoke → `ToolMessage` → re-invoke) is always manual unless using `create_agent`.

**State field initialization:** TypedDict state fields don't exist at runtime until explicitly populated. Always guard with `state.get("field", default)` or initialize in the input dict.

**Parallel execution:** Use `Annotated[Type, reducer]` for merging parallel branch outputs. Use `Send()` API for explicit fan-out.

**Rate limiting:** Free-tier APIs need `max_concurrency=1` on `.batch()` calls to avoid 429 errors.

## LangSmith Tracing

`LANGSMITH_TRACING=true` is set in `.env` — every LangChain/LangGraph invocation is automatically traced to the LangSmith project. Be aware of this when running notebooks; traces are sent to the cloud.

## Security Warning

**The `.env` file contains live API keys** (OpenAI, Anthropic, Tavily, HuggingFace, Mistral, Google, LangSmith). This file is currently NOT gitignored. Do not push this repository to any remote without first adding `.env` to `.gitignore` and rotating any exposed keys.

## Development Conventions

- **Notebook-first:** All source code lives in `.ipynb` files. There are no importable `.py` modules.
- **Learning journals:** Each module has a `learning.md` documenting design decisions, mistakes, and open questions. Update it after each session.
- **Template:** Use `concepts_learning_template.md` at the repo root as the starting point for new `learning.md` entries.
- **Python version:** 3.12 (see `.python-version`). Range: `>=3.11, <3.14`.
- **ADRs:** Before each build, write an Architecture Decision Record in `decisions/` using `adr_template.md`. Record ≥2 candidate architectures with a decision matrix (architect track constraint).

## Learning Workflow — Skills & Agents

All learning-acceleration tools live in `.claude/skills/` and `.claude/agents/`.

### Skills (invoke with `/skill-name`)

| Skill | When to use |
|---|---|
| `/session-prep [module\|next]` | **Start of every session** — surfaces last insight, open questions, focus recommendation |
| `/concept-check [module\|all\|concept]` | After reading or building — force active retrieval, find gaps |
| `/quick-recap [module\|yesterday\|all]` | Next day / 3 days later — spaced repetition recap card |
| `/explain-deep <concept>` | When a concept feels slippery — 6-layer Feynman breakdown |
| `/pattern-map [all\|primitive\|module]` | For synthesis — shows cross-layer pattern connections |
| `/notebook-debug` | When a cell errors — matches against known LangGraph gotchas |
| `/update-learning <module>` | End of every session — appends structured journal entry |
| `/annotate-notebook <module>` | After building — adds Input/Output/Design/Observation cells |
| `/new-module <name>` | Starting a new layer module — scaffolds directory, notebook, journal |
| `/adr [title\|reconcile N\|list]` | **Before a build** — record an architecture decision to `decisions/` |

### Agents (invoked via Agent tool or directly)

| Agent | When to use |
|---|---|
| `learning-coach` | Big-picture guidance — what to work on, gap analysis, practice experiments |
| `pattern-detective` | Deep cross-layer analysis — primitive inventory, mistake taxonomy, dependency graph |

### Recommended Session Flow

```
Session start:  /session-prep
During build:   /notebook-debug  (if errors hit)
                /explain-deep    (if a concept is unclear)
Session end:    /update-learning
                /annotate-notebook
Next day:       /quick-recap
Weekly:         /concept-check all
                /pattern-map
```
