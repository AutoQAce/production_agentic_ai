# The Agentic AI Production Bible
### Step-ordered build reference — v4 (Regulated-Finance Edition)

> **How to use this document.** Build in the order written. Each step says: what to implement from
> Fareed Khan's *"Building the 7 Layers of a Production-Grade Agentic AI System"* (Dec 2025,
> [article](https://levelup.gitconnected.com/building-the-7-layers-of-a-production-grade-agentic-ai-system-37ee5d941f1c)),
> what to **fix** while implementing it (never "later"), and what to **add** that the article doesn't have.
> Every step ends with a **Definition of Done** checklist — do not start the next step until it's green.
>
> **Rule 1:** The article is the backbone (~60% of a production system). Implement it — but apply each
> step's 🔴 fixes *inside that step*. Building the article verbatim and patching afterward is how the
> mislabeled circuit breaker and same-provider fallback survive into production.
>
> **Rule 2:** Anything marked 🔴-finance ships **before the first finance-facing demo**. No exceptions.
>
> **Honesty clause.** "Bible" is the working name, not a completeness claim. This spec is stack-specific
> (LangGraph + FastAPI + Postgres + Azure), opinionated, and decays fast. Verify version pins against
> primary docs (sources at the bottom). Last updated 2026-08-11.
>
> **v3.1 addendum (2026-07-19):** jurisdiction anchor corrected to **EU** (EU AI Act + EBA/ECB model-risk
> expectations primary; SR 11-7 reference discipline; MAS FEAT optional cross-map); **MiFID II suitability
> gate** added to Steps 10 & 18; **GDPR baseline** (lawful basis, purpose limitation, DPIA) added to
> Step 18. All additions are appended — nothing prior was removed.
>
> **v3.2 (2026-07-19):** defect fixes from review — Step 8 groundedness DoD was unsatisfiable at its own
> step (harness built at 8, gate activates at 13); Step 4 outbox wording disambiguated; Step 18's stale
> MAS-primary lines **replaced** (v3.1's append-only correction box created the very ambiguity it fixed);
> AI Act "plausibly high-risk" overclaim corrected against Annex III; **Appendix C deviation log** added —
> this spec is unproven until built against, and deviations get recorded, not hidden.
>
> **v4 (2026-08-11) — external-standards refresh.** Nothing about the architecture changed; the world
> underneath it did. Five upstream moves, all landed after v3.2 was written, all corrected **in place** at
> the step they affect (v3.2's lesson: no correction boxes bolted onto stale text). Ordered by what they
> cost if ignored:
>
> | # | What moved | When | Lands at | Cost of ignoring |
> |---|---|---|---|---|
> | 1 | **OWASP LLM Top 10 renumbered (2026 ed.)** + new **OWASP Top 10 for Agentic Applications (ASI01–10)** | 2026-08-04 | Steps 3, 9, 13, App. A | every OWASP ID cited in v3.x now points at a *different* risk; and the agentic list is the one that actually describes this system |
> | 2 | **EU AI Act Digital Omnibus** — Annex III high-risk deferred to **2027-12-02**; **Art. 50 transparency live since 2026-08-02** | Council 2026-06-29 | Step 18 | v3.2's classification reasoning holds but its *timeline* is now wrong in both directions — the distant deadline moved further out, the one that actually binds already passed |
> | 3 | **MCP spec 2026-07-28** — stateless core, handshake removed, **OAuth 2.1 + PKCE mandatory** | 2026-07-28 | Step 12 | Step 12 specified no auth at all; the spec now supplies one, and it is not optional for HTTP deployments |
> | 4 | **OTel GenAI semconv** → own repo (v1.42.0), **agent-level spans**; still `Development`, no 1.0 | 2026-06-12 | Step 7 | you'd instrument LLM calls and miss the agent/tool/memory span tree — the part that makes an *agent* debuggable |
> | 5 | **LangGraph 1.2** — per-node timeouts in `add_node()` | 2026-05-11 | Steps 4, 11 | not a risk, a freebie: Step 4's timeout DoD gets cheaper |
>
> **What did *not* change — and that is the finding.** Every 🔴 in Appendix A still stands. Circuit breakers,
> cross-provider fallback, transactional audit, HITL, tenancy-from-day-one, model-risk governance: three
> weeks of upstream churn moved none of them. The architecture was aimed at the right things; only the
> citations rotted. That is what the honesty clause predicted and why Step 20's quarterly "update this
> document" line exists — **v4 is that cycle firing early, not a redesign.**

---

## Phase map

| Phase | Steps | What you have at the end | Scale tier |
|---|---|---|---|
| **A — Backbone** (the article, corrected) | 1–8 | Working single-agent app: API, auth, DB, agent, memory, streaming, metrics, evals, load-tested | T1 |
| **B — Agentic hardening** | 9–13 | Guardrails baseline, HITL gate, durable execution, MCP tools, governed RAG + memory | T1.5 |
| **C — Scale-out** | 14–16 | Multi-replica: Redis everywhere, queue/outbox live, deployed on Azure Container Apps | T2 |
| **D — Governance & finance readiness** | 17–20 | Change management, model risk governance pack, feedback loop, drills scheduled | T3 |

Scale tiers: **T0** notebook · **T1** single node, docker-compose (the article's target) ·
**T2** stateless replicas behind LB, state in Redis/Postgres/queue (**the real production floor**) ·
**T3** platform: autoscaling, multi-tenant, full guardrails + eval gates + governance loop (**where a
regulated capstone lands**).

**The three axes you are always monitoring:**
1. **Agent behavior** — reasoning accuracy, tool-use correctness, memory consistency, safety boundaries.
2. **System reliability** — latency, availability, throughput, cost, failure recovery.
3. **Governance health** — validated, auditable, within budget, passing adversarial tests *this month*.
The article instruments (2) well, (1) barely, (3) not at all. This document builds all three.

---

# PHASE A — Build the article's backbone (corrected as you go)

## Step 1 — Foundation: modular codebase, config, containers *(article Layer 0)*

**Implement from the article:**
- Modular `app/` package layout, prompts-as-assets, per-env config, non-root Docker user, entrypoint secret-check.

**Fix while implementing:**
- 🔧 Config via `pydantic-settings` `BaseSettings`, secrets typed as `SecretStr` (no leaks in logs/tracebacks).
- 🔧 Compose DB image: `pgvector/pgvector:pg16`, **not** `postgres:16-alpine` (memory in Step 5 needs pgvector — cheaper to start right).
- 🔧 Add **Alembic** now; never use `SQLModel.metadata.create_all` beyond a throwaway prototype.

**Add (article doesn't have):**
- ➕ Pin base image by digest (`python:3.12-slim@sha256:…`); SBOM (`syft`) + scan (`trivy`) in CI.
- ➕ **Version every prompt file** (semantic version + changelog). Cheap today, painful retrofit later; Step 17 depends on it.
- ➕ `.env` is dev-only; note in README that prod secrets go to Azure Key Vault (Step 16).

**Definition of Done**
- [ ] `docker compose up` gives app + pgvector Postgres, non-root, secrets checked at entry
- [ ] `alembic upgrade head` creates the schema; no `create_all` anywhere
- [ ] CI builds image, generates SBOM, trivy scan passes
- [ ] Prompts live under `app/prompts/` with version headers

---

## Step 2 — Data persistence *(article Layer 1)*

**Implement from the article:**
- SQLModel entities + Pydantic DTOs with strict DTO/entity separation (never expose `hashed_password`).
- Async engine with `pool_pre_ping` + `pool_recycle`.

**Fix while implementing:**
- 🔧 Every schema change is an Alembic migration from day one.

**Add:**
- ➕ **Idempotency table** (used by Step 4 for retried mutations).
- ➕ **Audit-event table, append-only, hash-chained** (🔴-finance). Schema now, writers in Step 4, governance in Step 18. Columns: actor, tenant, action, tool, input-hash, output-hash, prompt-version, model-snapshot, prev-hash, ts.
- ➕ **Tenant column + row-level security posture** on every user-data table (🔴-finance). Retrofitting tenancy is a rewrite.
- ➕ **Erasure path design note:** deletion must cascade to relational rows **and** vectors **and** mem0 memories (implemented Step 13; designed here so schemas allow it).
- ➕ DR targets on paper: **RPO ≤ 15 min (PITR), RTO ≤ 4 h**; checkpointer + audit tables in scope. Drills scheduled in Step 20.

**Definition of Done**
- [ ] DTOs never leak entity internals (test asserts it)
- [ ] Audit + idempotency tables migrated; audit table has no UPDATE/DELETE grants
- [ ] Every table with user data carries `tenant_id`
- [ ] `DR.md` states RPO/RTO and what's in scope

---

## Step 3 — Web/app security *(article Layer 2 — the web half)*

**Implement from the article:**
- JWT auth, bcrypt password hashing, CORS, Pydantic input validation, rate limiting.

**Fix while implementing:**
- 🔧 JWT: **≤15-min access tokens + refresh tokens**, asymmetric signing (**RS256/EdDSA**), and use the `jti` claim for a revocation denylist (in-memory now, Redis in Step 14). The article's HS256 + 30-day token with no revocation is not acceptable.
- 🔧 Rate limiting: design keys as **per-user/tenant + per-IP** now even while the store is in-memory (T1 only); the store moves to Redis in Step 14. IP-only breaks behind proxies/NAT.
- 🔧 Know what this step is **not**: the article's XSS-regex "sanitization" is web hygiene, not agent security. Agent security is Step 9. Do not let this step create false confidence.

**Add:**
- ➕ CI security gates: `pip-audit`, `gitleaks`, `trivy`, SAST, Dependabot. Supply chain is **LLM04:2026** *(v4 — was LLM03 in the 2025 list; the 2026 edition renumbered it, and LLM03 is now Excessive Agency)*, and **ASI04 Agentic Supply Chain Compromise** extends it to the artifacts this system pulls at runtime: MCP servers, tool definitions, and prompt files are supply chain too, not just Python packages.
- ➕ Egress allowlist posture documented (enforced at deploy, Step 16): a compromised agent must not be able to call arbitrary hosts.

**Definition of Done**
- [ ] Access token expiry ≤15 min; refresh + revocation path works (test)
- [ ] Rate-limit key = (tenant, user, ip); limits configurable per env
- [ ] CI fails on high-severity dependency/secret findings

---

## Step 4 — Service layer & fault handling *(article Layer 3)*

**Implement from the article:**
- Model registry, Tenacity retry with exponential backoff + jitter, pooled DB access.

**Fix while implementing — both are 🔴, both are correctness bugs in the article:**
- 🔴 **Real circuit breaker** (`pybreaker` or `purgatory`) **per provider**: opens after N failures → fails fast → half-opens to probe recovery. The article's `while models_tried < total` loop is retry+fallback, **not** a circuit breaker; a dead provider keeps getting hammered.
- 🔴 **Cross-provider fallback registry.** The article's chain is gpt-4o → gpt-4o-mini — all OpenAI, so one OpenAI outage kills every "fallback". Use different providers:

  | Role | Primary | Fallback (different provider) | Cheap/fast tier |
  |---|---|---|---|
  | Reasoner / agent | Azure OpenAI GPT-5 | Anthropic Claude Opus 4.8 / Sonnet 5 | GPT-5-mini / Claude Haiku 4.5 |
  | Judge (eval) | strong model, **pinned snapshot** | second-family judge for bias checks | — |
  | Router / classifier | small fast model | — | Haiku 4.5 / GPT-5-mini |

  Pin model **versions** — behavior drifts across snapshots (Step 17 owns drift).

**Fix:**
- 🔧 **No fire-and-forget side-effects.** The article's `asyncio.create_task` memory write loses data on crash. Route memory writes and **audit events** through a **transactional outbox**. *(v3.2 — precise wording, the two sentences this replaces read as contradictory:)* the **outbox insert commits in the same DB transaction as the state change it records** — that is what makes it "transactional," and it is the 🔴-finance guarantee (no committed action without its audit event, ever). A relay (in-process loop at T1, queue worker at Step 14) then moves events from the outbox to the append-only, hash-chained audit table with **at-least-once delivery + idempotent apply**. So: capture is synchronous-and-atomic; delivery to the audit table is asynchronous-but-guaranteed. An audit trail with gaps is worse than none in front of a regulator — and this design makes gaps structurally impossible rather than operationally unlikely.

**Add:**
- ➕ Timeouts on **every** LLM/tool call; idempotency keys (Step 2's table) on retried mutations; bulkheads (separate pools for LLM vs DB vs tools); graceful shutdown draining in-flight requests. *(v4 — LangGraph 1.2, 2026-05-11, added **per-node timeouts directly in `add_node()`**; use them for the graph-level bound instead of hand-rolling `asyncio.wait_for` wrappers. The per-call timeout on the client still applies — node timeout bounds the step, client timeout bounds the call.)*

**Definition of Done**
- [ ] Kill a provider in a test → breaker opens, requests fail fast, fallback provider serves, breaker half-opens on recovery
- [ ] Fallback chain crosses providers (test asserts registry order)
- [ ] Crash mid-request → outbox replays memory/audit writes; nothing lost
- [ ] No LLM/tool call without a timeout (lint/test enforced)

---

## Step 5 — The agent *(article Layer 4)*

**Implement from the article:**
- Stateful LangGraph ReAct agent, `AsyncPostgresSaver` checkpointer, tool node, prompts-as-assets, mem0 long-term memory, Langfuse callback.

**Fix while implementing:**
- 🔧 Context management: the article's `trim_messages` (last-N) silently drops facts. Add **summarization/compaction** of older turns; keep a seam for context offloading.
- 🔧 Keep graph composition clean — the roadmap's target is multi-agent (supervisor + sub-agents, adversarial debate, risk/PM roles); don't weld tool logic into the graph.

**Add:**
- ➕ **Stream intermediate steps** (tool calls, reasoning summaries), not just final tokens — UX and debuggability.
- ➕ Mount the **guardrail interfaces** now (input hook before the agent, output hook after, tool-permission check inside the tool node). Implementations land in Step 9 — but the call sites exist from day one so Step 9 is a plug-in, not a refactor.

**Definition of Done**
- [ ] Multi-turn conversation survives process restart (checkpointer proof)
- [ ] Long conversation compacts instead of truncating (test with 100+ turns)
- [ ] Tool calls stream to the client as they happen
- [ ] Guardrail hook points exist and are exercised by a no-op implementation

---

## Step 6 — API gateway *(article Layer 5)*

**Implement from the article:**
- Versioned routers, dependency-injected auth, SSE streaming, session model, lifespan startup/shutdown, custom validation errors.

**Fix while implementing:**
- 🔧 SSE is fine for one-way tokens at T1. Note the T2 constraint now: streaming across replicas needs a Redis pub/sub backplane (Step 14); interruptible/bidirectional UX wants WebSockets.

**Add:**
- ➕ **Feedback capture endpoints as part of the API contract**: per-response 👍/👎 + reason code, correction submission, escalate-to-human. They feed Step 19; a system with no feedback intake cannot improve on evidence.

**Definition of Done**
- [ ] `/v1/...` routes; auth via DI; SSE streams tokens + tool events
- [ ] Feedback endpoints store (trace_id, verdict, reason, correction) per tenant

---

## Step 7 — Observability *(article Layer 6)*

**Implement from the article:**
- Prometheus metrics, structlog middleware binding user/session context, Grafana-as-code, cAdvisor, `/health` with DB check.

**Fix while implementing:**
- 🔧 `starlette-prometheus` is stale → `prometheus-fastapi-instrumentator`.
- 🔧 Adopt **OpenTelemetry GenAI semantic conventions**: `gen_ai.request.model`, `gen_ai.usage.input/output_tokens`, `gen_ai.response.finish_reasons`; add **TTFT**, tokens/sec, per-subtask spans. One OTel pipeline → Grafana/Tempo/Loki or Azure Monitor, plus Langfuse.
- 🔧 *(v4)* **Instrument the agent, not just the LLM call.** The conventions now model a whole run as a span tree via `gen_ai.operation.name`: `create_agent` / `invoke_agent` / `invoke_workflow` / `execute_tool` / `retrieval` / `plan` / memory ops. A trace containing only chat-completion spans cannot answer "which tool call went wrong on turn 4" — which is the only question you ask in an agent incident. Emit the agent-level spans from Step 5's graph nodes.
- 🔧 *(v4)* **Pin the semconv version and expect churn.** `gen_ai.*` moved out of the core semantic-conventions repo into its own GenAI repo (as of v1.42.0, 2026-06-12) precisely so it can move faster than core — and **every `gen_ai.*` attribute is still `Development` status, none Stable, no 1.0.** So: record the semconv version you built against in the repo, keep attribute names behind one mapping module rather than sprinkled through call sites, and treat a semconv bump as a change requiring the Step 17 review. Building directly against a pre-stable spec is fine; building against it *unversioned and un-abstracted* is how dashboards silently go blank.
- 🔧 **Don't capture prompt/response content by default** — sampling + redaction + retention gates (privacy).

**Add:**
- ➕ **Prompt version + model snapshot on every trace** — makes bad rollouts one-query diagnosable; Step 17 depends on it.
- ➕ **SLOs + alerts, not just dashboards**: availability, p95 latency, TTFT, error rate, cost/request — plus (wired as they come online) guardrail catch-rate (Step 9), HITL queue latency (Step 10), eval-score trend and dataset age (Steps 8/19), per-tenant budget burn (Step 15).

**Definition of Done**
- [ ] Every request → OTel trace with GenAI attributes + prompt/model version
- [ ] *(v4)* A single run renders as a span tree (`invoke_agent` → `execute_tool` / `retrieval` children), not a flat list of chat completions
- [ ] *(v4)* Semconv version recorded in-repo; attribute names live in one module
- [ ] TTFT and end-to-end latency separately visible
- [ ] Alert rules fire (tested) for availability, p95, error rate, cost/request

---

## Step 8 — Evaluation & load *(article Layer 7)*

**Implement from the article:**
- LLM-as-judge with structured rubric (score + reasoning), multiple metrics, scores pushed to Langfuse, concurrent load test.

**Fix while implementing:**
- 🔧 Post-hoc grading → **Eval-Driven Development with a CI gate**: **golden dataset** (start 100–200 cases, grow toward 500–2,000), run per-PR via DeepEval + pytest (Promptfoo for prompt/model-matrix sweeps). Tolerance bands + **pinned judge model** + stable sample so non-determinism doesn't flake the build. **Block merge on regression.**
- 🔧 Add **agent-specific evals**: trajectory/tool-use correctness, groundedness/faithfulness vs retrieved context (RAGAS), task completion — not just toxicity/hallucination. Calibrate the judge; periodically cross-check with a second-family judge. *(v3.2 sequencing note: the groundedness **harness** is built here, but its CI **gate** stays dormant until Step 13 — there is no retrieval pipeline yet to ground against. A DoD must be satisfiable at its own step.)*
- 🔧 Load test: run from an **Azure** box (not the article's EC2), add **ramp-up + soak** to catch leaks and pool exhaustion; record success rate, p95/p99, TTFT, and a **failure taxonomy** (429 vs pool-exhausted vs timeout).

**Add:**
- ➕ Golden dataset is a **living asset** with provenance per case; the refresh pipeline arrives in Step 19 — structure cases for it now.

**Definition of Done**
- [ ] PR with a degrading prompt change is blocked by the eval gate (prove it once deliberately)
- [ ] Trajectory evals run on every golden case with tool use; groundedness harness implemented with its gate dormant *(v3.2 — activates at Step 13 when retrieval exists)*
- [ ] Soak test (≥1 h) shows flat memory + stable pool usage
- **🏁 Phase A complete = the article, corrected. This is T1. Do not demo finance features yet.**

---

# PHASE B — Agentic hardening (what makes it different from a web app)

## Step 9 — Guardrails working baseline 🔴 *(absent from the article)*

The article's biggest gap. Ship a **minimal working baseline**, not a stub — a stub tests nothing and
protects nothing.

***(v4 — the map changed, and this is the single most consequential update in v4.)*** Two lists now apply,
and v3.x cited only the first, by IDs that have since been reassigned:

1. **OWASP GenAI LLM Top 10 — 2026 edition** (pub. 2026-08-04, first edition weighted by real incident data,
   7.7K incidents at 25% against community vote at 75%). **Renumbered — do not carry v3.x IDs forward:**
   LLM01 Prompt Injection *(held #1)* · LLM02 Sensitive Information Disclosure · **LLM03 Excessive Agency
   (was #6 — biggest climb, driven entirely by agentic deployments)** · LLM04 Supply Chain · LLM05 Data &
   Model Poisoning · **LLM06 Unbounded Consumption (was #10)** · LLM07 Misinformation · **LLM08 Hidden
   Context Exposure (renamed from System Prompt Leakage; now covers all hidden operational context — system
   instructions, RAG schemas, policy logic)** · LLM09 Vector & Embedding Weaknesses · LLM10 Improper Output
   Handling *(was #5 — furthest fall, not because it's solved)*.
2. **OWASP Top 10 for Agentic Applications — ASI01–ASI10 (2026)**, new since v3.2. This is the list that
   actually describes what is being built here; the LLM list describes one component of it. The premise:
   an agent chains actions, so a single injection cascades into system-wide compromise rather than one bad
   answer. ASI01 Agent Goal Hijack · ASI02 Tool Misuse & Exploitation · ASI03 Agent Identity & Privilege
   Abuse · ASI04 Agentic Supply Chain Compromise · ASI05 Unexpected Code Execution · ASI06 Memory &
   Context Poisoning · ASI07 Insecure Inter-Agent Communication · ASI08 Cascading Agent Failures ·
   ASI09 Human-Agent Trust Exploitation · ASI10 Rogue Agents.

**Read the two together like this:** the LLM list tells you what a model does wrong; the ASI list tells you
what that does to *your system*. The controls below are unchanged in substance — the mapping is corrected,
and three of the ASI entries have no control in v3.x at all (flagged 🆕 below).

**Add:**
- ➕ **Input guardrail (LLM01 · ASI01 goal hijack):** injection/jailbreak classifier (Llama Guard / Lakera / NeMo Guardrails class) in front of the agent; hardened system prompt; **untrusted content (tool results, retrieved docs) structurally separated from instructions** and never executed as commands. *(v4)* The 2026 edition explicitly extends LLM01 to **cross-modal** injection and to **injection that persists via memory** — so the classifier runs on tool/retrieval output too, not only on the user turn (this is why Step 13's memory-write guardrail is part of the same control, not a separate nicety).
- ➕ **Output guardrail (LLM10:2026 improper output handling — *was LLM05 in v3.x*):** schema enforcement, PII redaction, content moderation, groundedness check before output reaches user, DB, or another tool. *(v4)* Scope now explicitly includes **ANSI/terminal escape sinks and auto-fetching renderers** — if agent output lands in a terminal, a markdown viewer, or anything that resolves URLs on render, that renderer is the sink you must sanitize for.
- ➕ **Tool permission layer (LLM03:2026 excessive agency — *was LLM06* · ASI02 tool misuse · ASI05 unexpected code execution):** deterministic per-tool allowlist, least-privilege scoped credentials per tool, sandboxed execution for anything that runs code (Azure Container Apps Sandboxes at deploy). *(v4)* Excessive Agency climbing to #3 on incident data is the clearest signal in the 2026 release, and it is a signal about **exactly this system**: the failures are real deployments where model output executed shell commands, called APIs, or ran DB transactions unchecked. This control and Step 10's HITL gate are the two that earn their keep.
- ➕ **LLM02 / LLM08:2026 (hidden context exposure, *was LLM07 system prompt leakage*) hygiene:** PII redaction both directions, no secrets in prompts, assume the system prompt is extractable. *(v4)* The rename widened the target: **RAG schemas, tool descriptions, routing rules, and policy logic leak too** — anything in context the user was never meant to see. Audit what is in context, not just the system prompt string.
- ➕ 🆕 *(v4)* **Agent identity (ASI03).** The agent must not act as an ambient superuser. Every tool call carries a scoped, attributable identity — per-tenant, per-tool, least-privilege — so "which principal did this" is answerable from the audit trail (Step 2) and privilege cannot be inherited sideways between tools. Step 12's OAuth 2.1 requirement is the mechanism for MCP tools; native tools need the same discipline.
- ➕ 🆕 *(v4)* **Unbounded consumption (LLM06:2026, up four places).** Financial DoS is now a top-6 risk: reasoning models make cost asymmetric — a cheap prompt buys expensive inference. Per-request token/step/tool-call ceilings and a hard recursion bound belong **here as a safety control**, not only in Step 15 as a cost concern. Step 15 governs spend; this bounds a single hostile request.
- ➕ 🆕 *(v4)* **Cascading failures + rogue agents (ASI08/ASI10).** Deferred deliberately while the system is single-agent — but the roadmap's target is supervisor + sub-agents with adversarial debate, and these two risks arrive *with* the second agent. Record the deferral (Appendix C) and revisit at the multi-agent step; ASI07 inter-agent communication becomes live at the same moment.
- ➕ 🆕 *(v4)* **Human-agent trust exploitation (ASI09)** pairs with Step 10: an approval UI that presents the agent's framing of an action, rather than the raw action, launders the agent's intent through a human rubber-stamp. The HITL approver must see the **actual tool call and parameters**, not a model-written summary of them.
- ➕ **Adversarial regression suite:** seed from garak / PyRIT probes + domain attacks ("transfer funds", "reveal another tenant's data", "drop the compliance disclaimer"). Runs **in CI on every guardrail/prompt change** and monthly on schedule (Step 20). Every incident becomes a permanent case. Guardrail catch-rate becomes an SLI (Step 7).

**Definition of Done**
- [ ] Known injection strings are blocked at input (suite proves it)
- [ ] Malformed/PII-bearing output is caught before egress
- [ ] Agent cannot invoke a tool outside its allowlist even when the prompt tells it to
- [ ] Adversarial suite in CI with an explicit pass bar
- [ ] *(v4)* Suite covers **both** maps: LLM Top 10 2026 IDs and ASI01–10, with the ASI multi-agent entries (07/08/10) explicitly marked deferred-with-a-date rather than silently absent
- [ ] *(v4)* A single request cannot exceed its token / step / tool-call ceiling (LLM06 — test with a recursion-baiting prompt)
- [ ] *(v4)* Injection embedded in a *tool result* is caught, not just injection in the user turn

---

## Step 10 — Human-in-the-loop approval gate 🔴-finance

**Add:**
- ➕ **Deterministic HITL gate before any high-impact/irreversible action** — in finance: any order, disbursement, or advice. Enforced in code **before the action reaches the wire**, never as a prompt instruction.
- ➕ LangGraph `interrupt()` for the pause; approval UI/endpoint records **who approved what, when** into the audit trail (Step 2's table via Step 4's outbox).
- ➕ Documented decision rights: which role may approve which action class (feeds Step 18 accountability).
- ➕ *(v3.1)* **MiFID II suitability gate on the advice path.** "Advice" is not one gate — before any
  advice-shaped output reaches the user, a **deterministic suitability check** runs: (1) **know-your-client**
  data present and current (investment knowledge/experience, financial situation, objectives, risk tolerance);
  (2) **risk-profile match** — recommended instrument/strategy within the client's assessed risk band;
  (3) **appropriateness** for non-advised/execution-style flows (knowledge & experience test). Missing or
  stale KYC → the agent must not advise; it degrades to information-only with a disclosed reason. The
  suitability decision (inputs, rule version, outcome) is written to the audit trail like an approval, and
  the HITL approver sees the suitability result before signing off. Governance of the suitability rules
  themselves lives in Step 18.

**Definition of Done**
- [ ] Sensitive tool call pauses the graph; nothing hits the wire pre-approval
- [ ] Approval + approver identity land in the append-only audit trail
- [ ] Rejection path returns a safe, compliant response to the user
- [ ] *(v3.1)* Advice output with missing/stale KYC is blocked and degrades to information-only (test)
- [ ] *(v3.1)* Suitability decision (inputs, rule version, outcome) lands in the audit trail per advice event

---

## Step 11 — Durable execution & long-running tasks

**Add:**
- ➕ Checkpoints ≠ durable execution. Use LangGraph durability modes (`sync` for at-least-once step persistence) so crashed runs **resume exactly where they left off** — chaining 10 steps at 85% each finishes ~20% of the time without this.
- ➕ Journaled side-effects: every external effect goes through the outbox/idempotency pair (Steps 2/4) so replays don't double-execute.
- ➕ Verifier gate on long-horizon runs: cheap check between major steps; fail fast instead of compounding.

**Definition of Done**
- [ ] `kill -9` mid-run → run resumes at the interrupted step, no duplicated side-effects
- [ ] HITL interrupts survive restarts (approve two days later, run continues)

---

## Step 12 — MCP tool interoperability

**Add:**
- ➕ Migrate hand-rolled tools to **MCP servers**; the agent consumes MCP. Collapses N×M integrations to N+M; adopted across Anthropic/OpenAI/Google/Microsoft/Amazon — the 2026 standard.
- ➕ Per-tenant MCP credential scoping; MCP tool calls carry the same allowlist + audit treatment as native tools (Steps 9/10 apply unchanged).
- ➕ *(v4)* **Build against the 2026-07-28 spec, not the older one** — it is a structural revision, and adopting the previous shape now means migrating twice:
  - **Stateless protocol core.** The `initialize`/`initialized` handshake is **removed**; protocol version, client info, and capabilities travel in `_meta` on every request. Header-based routing and cacheable list results follow from this. Practical effect: MCP stops being a session you hold open and becomes ordinary request/response — which is what makes it survive Step 14's move to multiple replicas without a sticky-session hack.
  - 🔴 **OAuth 2.1 + PKCE is mandatory** for all protected HTTP deployments, with HTTPS on every endpoint and discoverable authorization-server metadata. v3.x specified no MCP auth at all — this closes that hole with an actual RFC path rather than a hand-rolled one, and it is the concrete mechanism for Step 9's ASI03 agent-identity control. Wire tools to the enterprise IdP; do not invent a token scheme.
  - **Extensions framework** (reverse-DNS identifiers, independent versioning). Anything non-standard you need goes in an extension, versioned separately — not as a fork of the core protocol.

**Definition of Done**
- [ ] At least the existing tools served over MCP; agent runs unchanged
- [ ] MCP calls appear in traces and the audit trail like native tool calls
- [ ] *(v4)* Servers speak the 2026-07-28 spec: no handshake dependency, `_meta` carries protocol/client info
- [ ] *(v4)* Every protected MCP endpoint is HTTPS + OAuth 2.1/PKCE with discoverable AS metadata; an unauthenticated call is rejected (test)
- [ ] *(v4)* MCP tool calls are attributable to a scoped per-tenant principal in the audit trail (ASI03)

---

## Step 13 — RAG ingestion & memory governance *(absent from the article)*

Retrieval quality is upstream of every groundedness eval — garbage in the index makes RAGAS measure
garbage faithfully. And memory that is written but never governed is a persistent injection channel.

**Add — RAG/ingestion:**
- ➕ Ingestion pipeline as a first-class, idempotent, re-runnable component: load → clean → **chunking per document type** (semantic/structural for policies & prospectuses, not fixed 512-token windows) → metadata (source, tenant, effective-date, jurisdiction) → embed → upsert.
- ➕ **Embedder version is part of the index schema.** Changing embedding models invalidates the whole index: blue/green reindex (build new, eval on golden queries, cut over, burn-in). Never mix embeddings from two models in one index.
- ➕ **Hybrid retrieval (BM25 + vector) + reranker** as default; HNSW index (not IVFFlat) in pgvector.
- ➕ Effective-dating/supersession: a stale rate sheet retrieved confidently is a finance incident, not a UX bug.
- ➕ **Retrieval golden set** (query → expected passages) in the CI eval gate.

**Add — memory governance (mem0):**
- ➕ Memory-consistency evals: recall of stored facts, contradiction detection.
- ➕ Explicit conflict policy (newest-wins vs ask-the-user) — chosen, not accidental.
- ➕ Forgetting: TTL/decay for low-value memories; **erasure cascades** into vectors + memories (Step 2's design).
- ➕ **Poisoning defense (*(v4)* LLM05:2026 Data & Model Poisoning + LLM09 Vector & Embedding Weaknesses; **ASI06 Memory & Context Poisoning** is the agentic framing — v3.x's "LLM08" now points at Hidden Context Exposure and should not be carried forward):** memories originating from tool output / retrieved content are provenance-tagged untrusted and may alter agent *knowledge*, never agent *instructions*; a memory-write guardrail screens payloads before persistence. Poisoned memory outlives the session and masquerades as user history — treat it as more dangerous than one-shot injection.

**Definition of Done**
- [ ] Re-running ingestion is a no-op on unchanged docs
- [ ] Retrieval golden set passes; hybrid beats vector-only on it (measured)
- [ ] *(v3.2)* Groundedness (RAGAS) CI gate **activated** against the retrieval golden set — Step 8's dormant harness goes live here
- [ ] Erasure request removes rows + vectors + memories (test proves all three)
- [ ] Injected payload in a document cannot become an instruction via memory
- **🏁 Phase B complete. The system is now an *agentic* system, not a chat app with tools.**

---

# PHASE C — Scale-out to T2

## Step 14 — Externalize state: Redis + queue

**Fix (article breaks at >1 replica):**
- 🔧 In-memory rate limiter → **Redis-backed**, per-tenant/user/IP.
- 🔧 JWT denylist → Redis (Step 3's `jti` design plugs in).
- 🔧 SSE across replicas → **Redis pub/sub backplane** (stream started on replica A reachable via replica B).
- 🔧 Outbox tables → real **queue workers** (ARQ/Celery + Redis, or Azure Service Bus) draining memory/audit writes.
- 🔧 Kill every module-level singleton that assumes one process.

**Definition of Done**
- [ ] 3 replicas behind a LB: rate limits, revocation, and streaming all correct
- [ ] Queue worker restart loses nothing (outbox replay)

---

## Step 15 — Cost governance & caching

**Add:**
- ➕ **Per-tenant budgets + kill-switch** (soft alert → hard stop), cost/request as an SLI.
- ➕ **Semantic cache** for repeated queries + **provider prompt caching** (Anthropic prompt caching ≈ −90% cost / −85% latency on long stable prefixes — structure system prompts for it).
- ➕ Model routing: classifier sends simple queries to the cheap tier (Step 4's matrix).

**Definition of Done**
- [ ] Tenant hitting budget cap is throttled and alerted; nothing silently overspends
- [ ] Cache hit-rate visible; cost/request drops measurably on repeated workloads

---

## Step 16 — Deploy on Azure

**Add:**
- ➕ **Azure Container Apps** (scale-to-zero, KEDA autoscaling, **Sandboxes** for tool execution) → AKS at T3.
- ➕ **Azure Database for PostgreSQL Flexible Server** (+ PgBouncer transaction pooling), managed Redis.
- ➕ Secrets → **Key Vault via managed identity** — none in image/env/CI logs.
- ➕ Egress allowlist enforced (Step 3's design); WAF / API Management in front at T3.
- ➕ **IaC (Bicep/Terraform)** — the environment is reproducible from the repo.
- ➕ CI/CD gates in order: lint → tests → security scans → **eval gate** → **adversarial gate** → build → deploy.

**Definition of Done**
- [ ] `terraform/bicep apply` from a clean subscription reproduces the environment
- [ ] Zero secrets in image or env dumps (scan proves it)
- [ ] Pipeline blocks deploy on eval or adversarial regression
- **🏁 Phase C complete = T2, the real production floor.**

---

# PHASE D — Governance & finance readiness

## Step 17 — Prompt & model change management

Prompts and model snapshots are **deploy artifacts** with the same rollout discipline as code. Step 8's
gate catches regressions pre-merge; this step catches bad rollouts and drift in production.

**Add:**
- ➕ **Prompt registry:** versioned (Step 1), rendered-prompt hash logged per request (Step 7), changelog with rationale. "Which prompt answered this?" is always answerable in one query.
- ➕ **Canary/shadow rollout:** new prompt/model to 5–10% of traffic (or shadow: run both, serve old), automated comparison on eval scores + guardrail hits + cost + latency, **auto-rollback on threshold breach**. Finance rule: canary only on non-advice paths; advice-path changes require full eval + human sign-off (Step 18 decision rights).
- ➕ **Snapshot drift watch:** provider forces a snapshot upgrade → run full golden + adversarial suite against the new snapshot **before** cutover; treat as a change requiring the same approvals.
- ➕ **One-command rollback** to the previous prompt+model pair; drilled in Step 20.

**Definition of Done**
- [ ] A bad canary auto-rolls-back without human intervention (prove once)
- [ ] Every production response is attributable to exact prompt version + model snapshot

---

## Step 18 — Model risk governance pack 🔴-finance *(before any finance-facing demo)*

Controls (audit trail, HITL) are necessary but are **not governance**. *(v3.2 — this paragraph is now
written EU-primary directly; v3.1's approach of keeping the stale MAS-primary text with a correction box
appended created exactly the ambiguity a spec can't have.)* Jurisdiction anchors, in order: **primary —
EU AI Act + EBA/ECB model-risk expectations** (EBA Guidelines on internal governance & ICT/security risk
management; ECB supervisory expectations on model risk, with the TRIM discipline as the mindset);
**reference discipline — SR 11-7** for MRM structure regardless of geography; **optional cross-map —
MAS FEAT** (its F/E/A/T decomposition remains a useful lens; keep the mapping doc, labeled supplementary).

**Add:**
- ➕ **Model inventory:** every model, prompt-set, guardrail classifier, and embedder — owner, purpose, limitations, approved-use boundary (model cards). The judge model and the injection classifier are models too.
- ➕ **Independent validation:** before launch and on material change, someone who didn't build it reviews eval methodology, challenges golden-set coverage, checks fairness on protected attributes (FEAT-F), reviews adversarial results — and writes a **validation memo**. For a capstone, a second reviewer + written memo satisfies the spirit; the artifact matters.
- ➕ **Accountability (FEAT-A):** named system owner; documented HITL decision rights (Step 10); written escalation path when agent and human disagree.
- ➕ **Transparency (FEAT-T):** AI-interaction disclosure, capability/limitation statements, deterministic disclaimer path on anything resembling advice (enforced by Step 9, not by prompt), and per-output explainability: trace shows sources, tool calls, prompt/model versions (Steps 6–8 + 17 make this free).
- ➕ **Audit trail governed:** append-only + hash-chain verified (Step 2/4), retention per regulatory schedule, gap monitoring alert.
- ➕ **Tenant isolation + residency as evidence:** RLS + per-tenant vector namespaces documented; data pinned to required region; retention/erasure paths written up as compliance artifacts.
- ➕ **EU AI Act as primary obligation** *(v3.2 — merged and corrected; the earlier "plausibly high-risk"
  wording overclaimed)*. EU users *are* in scope; do the risk classification now and **record it as a formal
  compliance-function decision**, not this document's assumption. The accurate starting point: **Annex III
  does not list investment advice as such** — its finance entries are creditworthiness assessment / credit
  scoring of natural persons and life/health insurance risk pricing. Unless features touch those, the more
  likely landing is **transparency obligations (Art. 50)** plus GPAI-model provisions upstream, with the
  heavy sectoral lifting done by MiFID II — which is precisely why the suitability gate (Step 10) matters
  more than AI Act tiering here. Build the one-page **conformity map** (obligation → mechanism → artifact)
  regardless: it costs little, covers either classification outcome, and the mechanisms already exist —
  risk-management (this step + Step 20), technical documentation (inventory + model cards), logging
  (Steps 2/4/7), human oversight (Step 10), accuracy/robustness evidence (Steps 8/9), data governance
  (Step 13).
- ➕ *(v4 — **the AI Act timeline moved in both directions; v3.2's reasoning stands, its dates do not**)*.
  Two changes, and they pull opposite ways:
  1. **High-risk obligations were deferred.** The **Digital Omnibus on AI** (Commission proposal 2025-11-19;
     Parliament 2026-06-16; Council final approval **2026-06-29**) pushes standalone **Annex III** high-risk
     obligations to **2027-12-02** and Annex I embedded-in-regulated-product systems to **2028-08-02**.
     Deferred, **not cancelled** — and since v3.2's analysis already concluded this system probably isn't
     Annex III (investment advice is not listed; the finance entries are creditworthiness/credit scoring of
     natural persons and life/health insurance pricing), the deferral mostly buys headroom on a branch you
     likely weren't on. Do not let it read as "the AI Act slipped, relax."
  2. 🔴 **Article 50 transparency is live — it applied from 2026-08-02, i.e. it is already in force as of
     this revision.** This is the obligation that actually binds this system, and it binds regardless of
     risk tier. Concretely: (a) **disclose AI interaction** — users must be told they are dealing with an
     AI system; (b) **Art. 50(2) machine-readable marking** of AI-generated content in a detectable format;
     (c) the **Code of Practice on Transparency of AI-generated Content** — confirmed adequate by the
     Commission, with final Guidelines published July 2026 — is the compliance vehicle: adhere to it and
     you have a presumption-of-conformity story instead of an argument. (d) A grace window runs to
     **2026-12-02**, but *only* for the marking/detection duty on systems placed on the market before
     2026-08-02 — a system first shipped now does not get it. (e) New **prohibited-practice** provisions
     also bite **2026-12-02**.
  **What this changes here:** transparency stops being a FEAT-T nicety three bullets up and becomes a dated
  legal obligation with an artifact attached. The disclosure and disclaimer path is already specified
  (enforced deterministically at Step 9, not by prompt) — what's missing is (i) machine-readable marking of
  generated output, (ii) a recorded decision on Code-of-Practice adherence, and (iii) both mapped in the
  conformity map. Cheap now; a live finding later.
- ➕ *(v3.1)* **EBA/ECB model-risk expectations:** align the MRM framework's vocabulary and review cycle with
  EBA internal-governance and ICT/security guidelines and ECB supervisory expectations on model risk —
  materiality-tiered validation depth, documented model-change policy (Step 17 is the mechanism), and
  findings tracked to closure with owners and dates (Step 20 quarterly cycle is the vehicle).
- ➕ *(v3.1)* **GDPR baseline** — the erasure cascade (Steps 2/13) is necessary but not the whole EU picture:
  (1) **lawful basis** documented per processing purpose (KYC data, conversation memory, feedback traces,
  eval datasets each get an explicit basis); (2) **purpose limitation** — production personal data does not
  flow into golden sets or adversarial suites without anonymization/pseudonymization and a documented basis
  (constrains Step 19's annotation pipeline); (3) **DPIA** for the AI processing of personal data —
  completed before launch, revisited on material change (Step 17 triggers it), filed alongside the
  validation memo; (4) data-minimization check on memory writes (does the agent *need* to remember this?)
  wired into Step 13's memory-write guardrail.
- ➕ *(v3.1)* **MiFID II suitability governance** (the runtime gate is Step 10; this governs it): suitability
  rule-set is a versioned, inventoried artifact with an owner (same registry discipline as prompts, Step 17);
  changes to suitability logic require independent review + sign-off; periodic back-testing of suitability
  decisions against outcomes in the quarterly revalidation (Step 20); **suitability-report generation** per
  advice event retained per MiFID record-keeping schedule alongside the audit trail.

**Definition of Done**
- [ ] Inventory covers 100% of models/prompts/classifiers/embedders in production
- [ ] Signed validation memo exists for the current release
- [ ] FEAT mapping doc: each principle → the mechanism implementing it
- [ ] Audit hash-chain verification job runs and alerts on gaps
- [ ] *(v3.1)* AI Act risk classification recorded; conformity map (obligation → mechanism → artifact) exists
- [ ] *(v4)* **Art. 50 compliance evidenced — it is in force, not upcoming:** AI-interaction disclosure on every surface; AI-generated output carries machine-readable marking; Code-of-Practice adherence decision recorded; all three in the conformity map
- [ ] *(v4)* Conformity map states the **current** deadlines (Annex III → 2027-12-02, Annex I → 2028-08-02, prohibited practices → 2026-12-02) and is dated, so the next Omnibus-style shift is visibly stale rather than quietly wrong
- [ ] *(v3.1)* DPIA completed and filed; lawful basis documented per processing purpose
- [ ] *(v3.1)* Suitability rule-set versioned, owned, and in the model inventory; MiFID suitability records retained per schedule

---

## Step 19 — Continuous feedback loop

**Add:**
- ➕ Pipeline: flagged production traces (👎, escalations, guardrail near-misses, low judge scores — Steps 6/9) → **human annotation queue** → labeled → appended to golden set **with provenance**.
- ➕ Refresh target: **≥10% of the golden set per quarter**; **dataset age is a tracked metric** with an alert.
- ➕ Quarterly review: eval-score trend, HITL override rate, guardrail catch-rate trend → prompt/retrieval/model improvements, which re-enter through Step 17's canary path. The loop is closed.

**Definition of Done**
- [ ] A real 👎 trace travels the full path to a new golden case (prove once)
- [ ] Dataset-age metric live with an alert threshold

---

## Step 20 — Operating cadence & drills

The system is now built. This step makes sure it **stays** trustworthy. Four cycles:

| Cadence | What runs | Fails loudly when |
|---|---|---|
| **Per-request** | input guardrail → agent (least-privilege, HITL on sensitive) → output guardrail → transactional audit write → versioned trace | any deterministic control is bypassed |
| **Per-change** | tests → golden eval → adversarial suite → fairness checks → canary/shadow → promote or auto-rollback (+ human sign-off on advice paths) | eval/adversarial gate regresses |
| **Weekly/monthly** | SLI review (catch-rate, HITL latency & override rate, cost burn, eval trend, dataset age); triage flagged traces to annotation; **monthly adversarial run** | any SLI trends down 2 periods |
| **Quarterly** | revalidation (golden + fairness + adversarial vs current snapshots) with finding log; **DR restore drill**; **rollback drill**; inventory + FEAT accountability review; update this document — *(v4)* explicitly re-check the **external standards** it cites: OWASP LLM/ASI editions, MCP spec date, OTel GenAI semconv version, AI Act deadlines, framework majors | a quarter passes without a drill, **or the standards check is skipped** |

**Definition of Done**
- [ ] Calendar/automation exists for monthly + quarterly cycles (not intentions — schedules)
- [ ] First restore drill and first rollback drill completed and logged
- [ ] This document has an owner and a review date
- **🏁 Phase D complete = T3. The difference between "we shipped an agent" and "we operate one."**

---

## Appendix A — The 🔴 list (single view)

| 🔴 | Fixed at | Why non-negotiable |
|---|---|---|
| Real circuit breaker (not retry+fallback) | Step 4 | dead provider keeps getting hammered otherwise |
| Cross-provider fallback | Step 4 | one provider outage must not kill all fallbacks |
| Transactional audit writes (outbox) | Step 4 | audit trail with gaps is worse than none |
| Guardrails working baseline | Step 9 | prompt injection held OWASP LLM #1 in the 2026 edition; XSS regex is not a defense |
| *(v4)* Tool-permission layer as a top-tier control | Step 9 | Excessive Agency climbed to **LLM03:2026** on incident data — the failures are agents executing shell/API/DB actions unchecked |
| *(v4)* MCP OAuth 2.1 + PKCE on protected endpoints | Step 12 | mandated by the 2026-07-28 spec; v3.x specified no MCP auth at all |
| *(v4)* EU AI Act **Art. 50 transparency** (disclosure + machine-readable marking) | Step 18 | **in force since 2026-08-02** — applies irrespective of risk tier; the high-risk deferral does not touch it |
| HITL gate on sensitive actions | Step 10 | finance: no order/disbursement/advice without deterministic approval |
| Audit trail + tenant isolation schema | Step 2 | retrofitting tenancy/audit is a rewrite |
| Model risk governance pack | Step 18 | EU AI Act + EBA/ECB primary, SR 11-7 reference *(v3.2)* — launch-blocker for finance |
| *(v3.1)* MiFID II suitability gate on advice path | Steps 10 + 18 | advice without a suitability check is a regulatory breach, not a UX gap |
| *(v3.1)* EU AI Act conformity map + GDPR DPIA/lawful basis | Step 18 | EU is the operating jurisdiction — these are the primary obligations, not a contingency |

## Appendix B — Quick reference

**Fallback matrix:** see Step 4. **SLIs:** availability, p95, TTFT, error rate, cost/request, guardrail
catch-rate, HITL queue latency, eval-score trend, dataset age, per-tenant budget burn.
**DR:** RPO ≤ 15 min, RTO ≤ 4 h, quarterly restore drill. **Golden set:** grow 100→2,000 cases, ≥10%
refreshed/quarter. **Judge:** pinned snapshot, second-family cross-check. *(RPO/RTO and dataset sizes are
defensible defaults, not derived from your load — revisit at Step 16.)*

## Appendix C — Deviation log *(v3.2)*

This spec is **unproven until built against**. Its real grade is decided in contact with implementation:
some DoDs will turn out naive, some sequencing wrong, some "adds" gold-plating. That is expected — the
failure mode is not deviating from the spec, it's deviating **silently**. Rules:

1. Any DoD that can't be satisfied as written, any step built out of order, and any item skipped as
   gold-plating gets a row here **before** the workaround ships.
2. A deviation that survives one phase gets folded back into the spec text (with a version bump) or
   reverted — this table is a queue, not a graveyard.
3. Review this log in the Step 20 quarterly cycle alongside the finding log.

| Date | Step | Spec said | Reality said | Action taken | Spec updated? |
|---|---|---|---|---|---|
| 2026-08-11 *(v4)* | Step 9 | Guardrail baseline covers the OWASP maps in force | ASI07 (inter-agent comms), ASI08 (cascading failures), ASI10 (rogue agents) are unreachable while the system is single-agent — there is no second agent to compromise, so a control would be untestable theatre | Deferred to the multi-agent step (supervisor + sub-agents), where all three become live simultaneously. Recorded rather than silently skipped, per rule 1 | Yes — Step 9 states the deferral inline |
| 2026-07-25 | Step 7 → Step 1 | Observability/structured logging is Step 7, built after Foundation (Step 1) and Steps 2–6 | Config loading is itself part of the backbone (Phase A) and can fail or misbehave silently — it needs to be traceable from its first line, not instrumented only after it's "done"; logging can't be bolted on after the foundation, it has to wrap the foundation | Split into two sub-steps, in this order: (a) structlog logging plumbing (processors, renderer, `get_logger()`) so a logger exists to log to; (b) a custom exception hierarchy (base `AppException` + a catch-all handler for anything unclassified) that logs itself meaningfully through that plumbing when raised. Neither works without the other — exceptions can't self-log before logging exists, and logging alone doesn't give meaningful error taxonomy. Both now built before returning to Steps 2–6 | No — sequencing changed; revisit at Step 20 review per rule 3 |

## Sources
- Source article — Fareed Khan, *Building the 7 Layers of a Production-Grade Agentic AI System* (Level Up Coding, Dec 2025) — https://levelup.gitconnected.com/building-the-7-layers-of-a-production-grade-agentic-ai-system-37ee5d941f1c
- OWASP Top 10 for LLM Applications 2025 — https://genai.owasp.org/llm-top-10/
- *(v4)* **OWASP GenAI LLM Top 10 — 2026 edition** (pub. 2026-08-04) — https://genai.owasp.org/resource/owasp-genai-llm-top-10-2026/ · changes summary https://www.invicti.com/blog/web-security/owasp-llm-top-10-2026-whats-new
- *(v4)* **OWASP Top 10 for Agentic Applications 2026 (ASI01–10)** — https://genai.owasp.org/resource/owasp-top-10-for-agentic-applications-for-2026/
- *(v4)* **MCP specification 2026-07-28** — https://blog.modelcontextprotocol.io/posts/2026-07-28/ · migration notes https://aaif.io/blog/mcp-2026-07-28-whats-changing-and-how-to-migrate
- *(v4)* **EU AI Act Digital Omnibus** (high-risk deferral, Council approval 2026-06-29) — https://www.gibsondunn.com/eu-ai-act-omnibus-agreement-postponed-high-risk-deadlines-and-other-key-changes/
- *(v4)* **EU AI Act Art. 50 transparency** (applies from 2026-08-02) + Code of Practice on Transparency of AI-generated Content — https://digital-strategy.ec.europa.eu/en/faqs/transparency-obligations-under-article-50-ai-act · https://digital-strategy.ec.europa.eu/en/policies/code-practice-ai-generated-content
- *(v4)* OTel GenAI semconv — dedicated repo since v1.42.0 (2026-06-12), all `gen_ai.*` still `Development` — https://opentelemetry.io/docs/specs/semconv/gen-ai/
- *(v4)* LangGraph 1.2 (2026-05-11, per-node timeouts) — https://changelog.langchain.com/
- OpenTelemetry GenAI semantic conventions — https://opentelemetry.io/docs/specs/semconv/gen-ai/
- LangGraph durable execution — https://docs.langchain.com/oss/python/langgraph/durable-execution · https://www.diagrid.io/blog/checkpoints-are-not-durable-execution-why-langgraph-crewai-google-adk-and-others-fall-short-for-production-agent-workflows
- Model Context Protocol — https://www.anthropic.com/news/model-context-protocol · https://workos.com/blog/everything-your-team-needs-to-know-about-mcp-in-2026
- Azure Container Apps Sandboxes — https://techcommunity.microsoft.com/blog/appsonazureblog/introducing-azure-container-apps-sandboxes-secure-infrastructure-for-agentic-wor/4524131 · https://learn.microsoft.com/en-us/startups/build/ai/agents/scaling-agents
- Eval frameworks (DeepEval/Promptfoo/RAGAS) — https://aiml.qa/llm-evaluation-framework-benchmark-2026/
- Guardrails landscape — https://galileo.ai/blog/best-ai-agent-guardrails-solutions
- Semantic/prompt caching — https://www.truefoundry.com/blog/semantic-caching
- Production agents 2026 — https://mlflow.org/articles/building-production-ready-ai-agents-in-2026/
- MAS FEAT Principles + TRM Guidelines — https://www.mas.gov.sg/ (search "FEAT")
- *(v3.1)* EU AI Act (Regulation (EU) 2024/1689) — https://eur-lex.europa.eu/eli/reg/2024/1689/oj · https://artificialintelligenceact.eu/
- *(v3.1)* MiFID II suitability — ESMA Guidelines on certain aspects of the MiFID II suitability requirements — https://www.esma.europa.eu/ (search "suitability guidelines")
- *(v3.1)* GDPR (Regulation (EU) 2016/679) + DPIA guidance — https://eur-lex.europa.eu/eli/reg/2016/679/oj · EDPB DPIA guidelines https://edpb.europa.eu/
- *(v3.1)* EBA Guidelines on internal governance & ICT and security risk management — https://www.eba.europa.eu/ · ECB model-risk / TRIM supervisory expectations — https://www.bankingsupervision.europa.eu/
- Fed SR 11-7 Model Risk Management — https://www.federalreserve.gov/supervisionreg/srletters/sr1107.htm
- Adversarial tooling — garak https://github.com/NVIDIA/garak · PyRIT https://github.com/Azure/PyRIT
