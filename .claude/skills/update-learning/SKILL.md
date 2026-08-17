---
name: update-learning
description: Update the learning.md journal for a module after a notebook session. Reads the notebook and existing journal, then (A) fills any empty top-template sections (business problem, concept definitions, TL;DR, key takeaways, retrospective) from the notebook's intro markdown cells, and (B) appends a structured session entry covering concepts, design decisions, mistakes, open questions, and performance observations.
disable-model-invocation: true
---

The user wants to update the learning journal for a module. Arguments: $ARGUMENTS

## Instructions

### 1. Identify the target module

Parse $ARGUMENTS for a module name or path. If none provided, ask the user which module's `learning.md` to update (list existing module directories at the repo root).

Examples of valid arguments:
- `parallel_evaluation_robust_governance`
- `hierarchical_agent_teams`
- (empty) → ask the user

### 2. Read the current state

Read both files:
- `<module>/learning.md` — the existing journal (may already have entries)
- `<module>/<module>.ipynb` — the notebook to derive new insights from
- `concepts_learning_template.md` — the template at repo root (for structure reference if the journal is new/empty)

### 3. Analyze the notebook

From the notebook cells, extract two categories of information:

#### 3a. Template-fill content (from intro/overview markdown cells)
These fields populate the **top template section** of `learning.md` (the `# Journal Entry` block). Look specifically at early markdown cells — the module title cell, "Introduction", "The Core Concept", "Role in a Large-Scale System", "Business Problem", and similar framing cells:

- **Business / Problem Statement:** What production problem does this pillar solve? Why does it matter in agentic systems? Capture the real-world motivation, not just the code summary. Use the notebook's own language.
- **TL;DR bullets:** 3 short bullets — the three most important ideas a reader should walk away with.
- **What is `<X>`:** Each named concept (e.g., "What is Sharded Retrieval?", "What is Scattered Retrieval?") — 2–4 sentences defining it in plain terms from the notebook's framing.
- **How it differs from standard RAG / the naive approach:** The key contrast the notebook draws.
- **Key mechanisms:** The core technical ingredients (e.g., scatter → parallel fetch → gather → dedup → generate).
- **Key Takeaways (numbered):** 3 distilled lessons that will still be useful 6 months from now.
- **Session Retrospective:** Brief honest notes on what worked, what didn't, and what to do differently. If there's no prior context, write "N/A" for "What didn't" and "What to do differently".
- **Primary goal:** Infer from the notebook title cell or first markdown cell. One short phrase.
- **Confidence before/after:** Leave as `/10` placeholders — user fills these in.

#### 3b. Session-entry content (from code cells and cell outputs)
These fields populate the **appended `## Session:` entry** at the bottom:

- **What was built:** the core system or pattern implemented
- **Key design decisions:** non-obvious choices made (e.g., why `merge_dicts` over `operator.add`, why two-stage LLM invocation)
- **Mistakes or gotchas encountered:** anything that would have tripped up a reader
- **Open questions:** things left unresolved or worth exploring further
- **Performance observations:** any timing data, concurrency behavior, or API behavior noted in outputs
- **Concepts demonstrated:** LangGraph/LangChain/agentic AI patterns used

### 3c. Check which template sections are unfilled

Scan the existing `learning.md` top template for placeholder text:
- A section is **unfilled** if it contains only `> ` blockquote placeholders, bare `-` bullets, bare numbered items (`1.`, `2.`, `3.`), or `# placeholder` code blocks.
- A section is **already filled** if it has real prose or bullet text beyond the placeholder markers.

Only write to unfilled sections — never overwrite content the user has already added.

### 4. Write the journal update — TWO parts

#### Part A: Fill the top template (if sections are unfilled)

For each unfilled section identified in Step 3c, replace the placeholder content with real content drawn from Step 3a. Use this mapping:

| Template section | Source in notebook |
|---|---|
| `## Business / Problem Statement` | Intro/overview markdown cells describing the production problem |
| `### What is <Concept>?` | Definition cells / "Core Concept" section |
| `### How do they differ from standard RAG?` | Contrast paragraph in intro markdown |
| `### Key mechanisms` | Architecture / component list in intro markdown |
| `### Code sketch / pseudocode` | First representative code cell (the key node or chain) |
| `### Observations` | Any cell-output analysis or summary markdown cells |
| `## TL;DR` bullets | 3 bullets synthesised from the session |
| `## Key Takeaways` | 3 numbered lessons distilled from the whole notebook |
| `## Session Retrospective` | Honest assessment; infer from cell outputs and gotchas |
| `| Primary goal \|` | Notebook title cell or first markdown cell |

Keep filled sections exactly as-is.

#### Part B: Append the session entry (always)

Append a new dated session entry to `learning.md`. Follow this structure exactly:

```markdown
---

## Session: <today's date> — <one-line topic summary>

### What We Built
<2–3 sentences describing the system. Be specific: name the nodes, the pattern, the output type.>

### Core Concepts Demonstrated
- **<Concept name>:** <one-line explanation of how it was used here>
- (repeat for each concept — aim for 4–8 bullets)

### Key Design Decisions
- **<Decision>:** <Why this choice was made. What alternatives were rejected and why.>
- (repeat for each non-obvious decision)

### Mistakes / Gotchas
- <Describe each pitfall. Frame as "If you do X, Y happens. Fix: Z.">

### Performance Observations
<Any timing data, concurrency proof, or API behavior noted in cell outputs. If none, write "N/A".>

### Open Questions
- [ ] <Unresolved question worth investigating>
- (repeat for each open question)

### TL;DR
<One sentence. The single most important thing learned in this session.>
```

### 5. Also update `_index.md`

Add a new row to the session table in `_index.md` at the repo root. The table has **five columns** — match them exactly so the row stays aligned:

```markdown
| <date> | `<module>/<notebook>.ipynb` | <topic> | <TL;DR from above> | <shaky concepts or —> |
```

For the **Shaky Concepts** column, list any concept the user rated ≤ 2/5 confidence or a still-open question raised this session; use `—` if everything felt solid. This column is what the root `/sync-master` dashboard reads to flag concepts that stay shaky across multiple sessions, so don't omit it.

### 5b. Architect capture (decision-readiness)

The end goal is architect, so close the design loop too:
- If a **real design fork** happened this session (you chose among ≥2 viable approaches under a constraint) and there's no ADR for it, tell the user to run `/adr <title>` — the journal's Design Decision block captures the *what*; the ADR captures the *decision under constraint* and feeds the Design Decisions Log.
- If an ADR exists for this build, remind the user to run `/adr reconcile <NNNN>` to fill **predicted-vs-actual failure modes**.
- Note the **patterns touched** and suggest a decision-readiness level (D0 buildable → D1 tradeoffs known → D2 selectable → D3 decided in an ADR) so `/sync-master` can roll it up.

### 6. Report

Tell the user:
- **Top template:** which sections were filled in (list each section name) vs. which were already populated and left untouched
- **Session entry:** confirm the `## Session:` block was appended and give its TL;DR line
- **`_index.md`:** show the new row that was added
- **Open questions:** any unresolved questions from this session not already tracked in the journal's Open Questions list
