# Production-Readiness Checklist — the 7-Layer Lens

> **Purpose:** the Production Lens deliverable from the roadmap (read #30 *conceptually* right after Phase 1).
> This is **not** the #30 hands-on build — that stays in Phase 9. This is the one-line-per-layer scaffold you
> hold **every capstone** against, from the Phase 1 *Client Portfolio Assistant (v0)* onward: "read the
> destination first, then build toward it."
>
> Source: Fareed Khan, *Building the 7 Layers of a Production-Grade Agentic AI System* (63 min, 101 pp, Dec 2025).
> Skimmed 2026-07-19. Article target scale: ≤10K users. Stack: FastAPI + LangGraph + Postgres + Langfuse + Prometheus/Grafana.

## The two things production monitors (the frame)
Every layer below serves one of these:
1. **Agent behavior** — reasoning accuracy, tool-use correctness, memory consistency, safety boundaries, multi-turn context.
2. **System reliability/performance** — latency, availability, throughput, cost, failure recovery, dependency health.

A learning notebook only ever touches (1). Everything that makes it *production* is (2). That gap is the whole point of this lens.

---

## Layer 0 — Foundation (not one of the 7, but the article builds it first)
- **What:** modular codebase (`app/api`, `core`, `models`, `schemas`, `services`, `utils`, `evals`), per-environment config (`.env.development|staging|production`, `pydantic-settings`), containerization (Docker + compose).
- **Done looks like:** the capstone is not one notebook — it's a package where I can swap the LLM, the store, or the data source without touching business logic; secrets come from env, never code; `docker compose up` runs the whole stack.
- **P1 capstone check:** even v0 should separate the supervisor/sub-agent graph (`core/langgraph`) from the tools and from the API surface. Prompts live as `.md` assets, not f-strings in code.

## Layer 1 — Data Persistence
- **What:** SQLModel entities + Pydantic DTOs; Postgres-backed LangGraph checkpointer (`langgraph-checkpoint-postgres`) so agent state survives restarts.
- **Done looks like:** conversation threads and long-term memory persist in a real DB, not `InMemorySaver`/`InMemoryStore`; DTOs separate the wire schema from the DB schema so I never leak internal fields.
- **P1 capstone check:** the client's risk profile / mandate / preferences persist across sessions in a durable store — this is exactly the #4 long-term-memory piece, now with a real backend. **Audit angle:** every write is timestamped and attributable.

## Layer 2 — Security & Safeguards
- **What:** rate limiting (`slowapi`), input sanitization, JWT auth (`python-jose`, `passlib[bcrypt]`), CORS allow-list, context-window management as a safety boundary.
- **Done looks like:** every request is rate-limited, sanitized, and cryptographically verified *before it touches AI logic*; no endpoint is open; prompt-injection surface is considered.
- **P1 capstone check:** per-advisor / per-client isolation starts here — a JWT identity scopes which client's memory namespace you can read. **Regulated-domain angle:** PII redaction and a "no financial-advice claim without approval" boundary are safeguards, not features. (Full guardrail pipeline is Phase 6 #18 — here just reserve the seam.)

## Layer 3 — Service Layer (for AI agents) → *fault handling*
- **What:** connection pooling; LLM-unavailability handling via `tenacity` (exponential retry on `RateLimitError`/`APITimeoutError`); a model **registry with circular fallback** (gpt-4o → gpt-4o-mini) so a provider outage rotates to a backup instead of 500ing; circuit breaking.
- **Done looks like:** a single provider hiccup never reaches the user; retries are bounded and logged; there's always a fallback model; the LLM call is wrapped, not called raw.
- **P1 capstone check:** the market-data and holdings sub-agents call the LLM through one resilient `LLMService`, not `llm.ainvoke` directly. This is where the parallelism folder's *redundant-execution / hedged-request* muscle transfers.

## Layer 4 — Multi-Agentic Architecture
- **What:** stateful LangGraph agents (loop, retry, call tools, persist state); long-term memory (article uses `mem0ai`; you've built the LangGraph `Store` path in #4); tool calling; prompts-as-assets.
- **Done looks like:** agents remember facts across sessions, resume after a restart, and their tools are narrow and typed.
- **P1 capstone check:** **this is the core of the v0 capstone** — supervisor + holdings agent + market-data agent, with cross-session memory injected into the system prompt at runtime (`{long_term_memory}` placeholder). Short-term (thread) vs long-term (cross-thread) memory is the #3→#4 through-line made real.

## Layer 5 — API Gateway → *service layer / middleware surface*
- **What:** versioned auth endpoints (`/api/v1`), real-time streaming (SSE) of agent tokens, middleware pipeline.
- **Done looks like:** the agent is reachable as a versioned HTTP API with auth, and responses stream token-by-token rather than blocking; middleware attaches request/user/session context to every call.
- **P1 capstone check:** for v0 a thin FastAPI surface + the HITL approval gate exposed as an endpoint is enough; don't build the full gateway yet, just don't wire the graph so tightly that adding one is a rewrite.

## Layer 6 — Observability & Operational
- **What:** Prometheus metrics (`http_requests_total` counter, latency histograms → p50/p95/p99), context-aware structured logging (`structlog` with `user_id`/`session_id`), Grafana dashboards, Langfuse tracing, CI/CD (GitHub Actions → Docker build/push).
- **Done looks like:** I can answer "how fast, who's using it, where are errors" from a dashboard, and trace any failure back to a specific user/session; every deploy is automated and reproducible.
- **P1 capstone check:** you already have `LANGSMITH_TRACING=true` — that's the free first rung. **Audit angle:** context-aware logs *are* the immutable audit trail a regulated firm demands; design log lines as audit records from day one.

## Layer 7 — Evaluation & Stress (the proof wrapper)
- **What:** **LLM-as-a-Judge** with a Pydantic rubric (`score: float`, `reasoning: str`) grading Langfuse traces on dimensions like **hallucination**; stress test (article: 1,500 concurrent users on an EC2 box → 98.4% success, 1.2s avg latency, failures were provider 429s absorbed by the fallback).
- **Done looks like:** regressions are caught by an eval suite *before* users see them (AI is probabilistic — a prompt fix that helps one case silently breaks five); the system has a measured behavior under load, not a hope.
- **P1 capstone check:** full eval/guardrail rigor is Phase 6 (#16–#19) — here just internalize the demand: **every number the assistant states must trace to a source or it abstains** (zero hallucinated figures), and "done" is a gate the output passes, not a vibe. The stress test proves the *fault-handling* layer actually fires (the fallback log under load is the receipt).

---

## How to use this
Before each capstone build, walk these 8 rows and mark each: **already done / seam reserved / explicitly out of scope for now.** You will *not* implement all of them in P1 — the value is that every deferral is a **conscious** one, and you know which Phase brings it back (fault-handling ↔ redundant execution now, guardrails ↔ #18, eval ↔ #16–19, multi-tenant/audit ↔ #30/#31 hands-on). That's the architect move: hold the finished system in view while building the current slice.
