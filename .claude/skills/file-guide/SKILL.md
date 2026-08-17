---
name: file-guide
description: Write a line-by-line reference guide for one file in this repo, into docs/. For every line — plain-English analogy, what breaks if it's missing, the technical mechanism, why this way and not the obvious alternative, and where it fits in the production agentic AI system. Produces the docs/N_<file>_guide.md format used by this project.
disable-model-invocation: true
---

The user wants a line-by-line guide for a file. Arguments: $ARGUMENTS
(a path like `app/core/logging.py`, or a bare name like `middleware.py`, or empty.)

## Purpose

These guides are **personal reference documents**, not documentation for other people. The reader is
future-you, six months from now, reopening a file you wrote and asking "why is this line here?"

That reader does not need to be told what `import os` does. They need to be told **why this file
imports `os` when everything else uses pydantic** — and what broke the last time someone removed it.

The guide is finished when every non-obvious line has a defensible *reason* attached to it.

---

## 1. Resolve the target

Parse `$ARGUMENTS` into a single file path.

- A bare name → search the repo for it. If more than one matches, list them and ask which.
- Empty → list the files in `app/` that have no guide yet in `docs/`, and ask which one.
- A file that is mostly data (`__init__.py`, a `.gitkeep`, an empty module) → say so and stop. A
  guide for a file with nothing to decide is noise.

## 2. Read everything before writing anything

Do not start drafting until you have read:

1. **The target file, completely.** Every line, including comments and docstrings.
2. **Every file it imports from this repo**, and **every file that imports it.** A guide that
   explains a file in isolation gets the "where it fits" sections wrong. Use Grep to find both
   directions.
3. **Its tests**, if any exist.
4. **`docs/` — an existing guide**, to match the current house conventions. Read the most recently
   numbered one.
5. **`.env.example` and `pyproject.toml`**, when the file reads config or is affected by tooling
   settings.

## 3. Verify, don't assume

> **This is the rule that separates a useful guide from a plausible-sounding one.**

Every claim about behaviour must be something you **executed**, not something you inferred.

- Claims that a value is validated → construct the bad value and watch it raise.
- Claims about precedence or ordering → prove it (a throwaway script in the scratchpad is fine).
- Claims about what a library does → run it, or read the installed source in `.venv`. Not memory.
- Test counts, coverage numbers, line numbers → read them off a real command's output.
- If a claim can't be verified cheaply, either drop it or write it as an explicit open question.

When something you expected turns out false, **that discovery is the most valuable content in the
guide.** Give it a 🚨 callout near the top.

## 4. Structure

Use this skeleton. Skip a section only when the file genuinely has nothing for it.

````markdown
# <emoji> `<path>` — Line-by-Line Guide

> **Purpose:** A personal reference covering **every line** of <what this file is>.
> For each line: what it means in plain English, what breaks if you don't write it, the technical
> mechanism, why *this* way and not the obvious alternatives, and where it fits.
>
> **Written:** <date>, <what prompted it>.
> **Companion docs:** <links to related guides and what they cover instead>

---

## 🚨 Read this first — <the bugs / surprises this file's design encodes>

A table of the real problems that shaped this file. Symptom in one column, cause in the other.
Then one bolded **meta-lesson** sentence.

Skip this section only if the file has no history of breaking. Most do.

---

## 📚 Table of Contents

| § | Section | Lines |
|---|---|---|
| 1 | [What this file is](#...) | — |
| 2 | ... | 27–39 |

Line ranges are mandatory — they are how you navigate back from the code to the guide.

---

## 1. What this file is

🍕 **Plain terms:** one analogy for the whole file. Physical world, no jargon.

🔧 **Technical:** one paragraph, precise.

### The one idea behind the whole file

> A single italicised sentence that every later decision traces back to.

---

## 2..N. <one section per logical block, in file order>

Quote the actual code first, then explain it.

---

## <N+1>. SOLID scorecard  *(when the file has real structure)*

A five-row table, **plus** a subsection titled "Where SOLID is deliberately NOT applied."

---

## <N+2>. Where this fits in the <system>

An ASCII diagram showing this file's place, plus a table contrasting an ordinary web app with an
agentic AI system on the axis this file cares about.

---

## <N+3>. How to extend it

The two or three changes most likely to be needed next, each shown as the minimal diff.
Explicitly state what is *not* built yet and why deferring was correct.

---

## <N+4>. Cheat sheet

A fenced plain-text block — no prose. Scannable in five seconds. Always end with a `NEVER` list.

### Verification commands

The exact commands that prove the guide's claims.

---

## 📎 Related files

| File | Relationship |
|---|---|

---

*Last updated: <date> | Based on `<path>` of the `<project>` project*
````

## 5. The annotation vocabulary

Every explanation is built from these markers. Use them consistently; they are how the eye scans.

| Marker | Answers | Rules |
|---|---|---|
| 🍕 **Plain terms** | What is this, to someone with no context? | A **physical-world** analogy — a reception desk, a filing cabinet, a stack of transparencies. It must *predict behaviour*, not just label it. If the analogy would mislead someone reasoning from it, it's the wrong analogy. |
| 🔧 **Technical** | What actually happens? | Name the real mechanism: the method, the PEP, the RFC, the evaluation order. Precise, no hedging. |
| ❓ **What if we don't write it** | What breaks? | A **concrete** failure, with the error message or the wrong behaviour. "It would be less safe" is not an answer. "The app boots and signs every token with the string `change-me`" is. |
| ❓ **Why this way only** | Why not the obvious alternative? | Name the alternative, then give the specific reason it loses. If there is no meaningful alternative, drop this marker rather than invent one. |
| ⚠️ **Known trap / limitation** | What will bite later? | Maintenance couplings, deliberate stopping points, deferred work. Say plainly that it was a **choice**, so future-you doesn't read it as an oversight. |
| ✅ **Solves** | The one-line payoff. | Optional; use when the section ran long. |
| 🎯 **Agentic AI angle** | Why does this matter *here*? | Only when it genuinely differs from an ordinary web service. Never force it. |

Close a section with a blockquote when it teaches something reusable:

> **The transferable idea:** prefer data over branches. When a decision is a lookup, write a lookup.

Use these sparingly — three or four per guide. They are the sentences you want to remember.

## 6. Rules for the writing itself

**Density.** Explain the *decisions*, not the syntax. A line like `PROJECT_NAME: str = "..."` needs
one row in a table. A line like `frozen=True` needs a page, because it encodes a concurrency
argument.

Group the boring lines. Never pad the interesting ones.

**Grounding.** Every claim points at something real: a line number, a test name, a command's output,
a spec section. Prefer "verified by `test_settings_are_frozen`" over "this is safe."

**Alternatives.** For each significant decision, name what was rejected and why. A guide that only
justifies what exists teaches nothing about judgment.

**Honesty.** Write the limitations down. Deferred work, known debt, and "this is a proxy for the
thing we actually want to measure" belong in the guide, with the reason and the trigger for
revisiting.

**Tone.** Direct. No "simply", no "just", no "of course". If it were obvious the guide wouldn't
exist. Second person where it helps ("you'd spend an afternoon on it").

**Length.** Whatever the file earns. A 250-line module with real design in it earns a long guide.
Don't stretch a thin file to match.

## 7. Naming and placement

- Write to `docs/<N>_<name>_guide.md`, where `<N>` is the next unused number in `docs/` and `<name>`
  identifies the file (`config_py`, `logging_py`, `env`, `pyproject_toml`).
- Pick one emoji for the H1 that isn't already used by another guide in `docs/`.
- Cross-link: if an existing guide covers neighbouring ground, link to it from the new guide **and**
  add a link back from the old one.

## 8. Before reporting done

- [ ] Every claim in the guide was verified by running something — none inferred
- [ ] Line numbers in the TOC match the current file
- [ ] Every code block quotes the file **exactly** (copy it, don't retype it)
- [ ] Every relative link resolves (`../app/core/x.py`, `./1_env_guide.md`)
- [ ] Every significant decision names the alternative it beat
- [ ] Limitations and deferred work are written down, not hidden
- [ ] The cheat sheet is scannable without reading any prose above it

Then report: the path written, the section count, and **anything you discovered while verifying that
contradicts what the code or a previous guide claims** — that is the finding worth surfacing, not the
word count.
