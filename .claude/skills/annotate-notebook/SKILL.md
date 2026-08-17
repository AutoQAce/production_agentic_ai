---
name: annotate-notebook
description: Transform a Jupyter notebook into a cohesive, self-explanatory document. Inserts Input/Output/Design Decisions/Observation annotations after every code cell, extends the final output cell with Business Problem closure and Pattern Applicability, appends a Pattern Analysis section, and reforms any existing markdown cells that break the narrative flow.
disable-model-invocation: true
---

The user wants to annotate a notebook with explanatory markdown cells. Arguments: $ARGUMENTS

## Reference Pattern

Every Python code cell in this project should be followed by a markdown cell with this exact structure (taken from `parallel_evaluation_robust_governance/parallel_evaluation_robust_governance.ipynb`):

```markdown
## <Action-oriented title describing what this cell does>

**Input:** <What the cell receives — function arguments, state fields read, or "No runtime input" for definitions>

**Output:** <What the cell produces — return value, side effect, printed output, or object created>

**Design Decisions:**
- **<Decision or component name>:** <Why this choice was made. What alternatives exist. What problem it solves.>
- (repeat for each non-obvious decision — aim for 2–5 bullets)

**Observation:** <The single most important insight about this cell — a pattern, a gotcha, or a consequence the reader should carry forward>
```

Rules for the content:
- Title uses `##` (h2), never `#` or `###`
- Title is action-oriented: "Defining the Data Contract", not "Pydantic Models"
- **Input** and **Output** are on the same line as the bold label (not a new line)
- **Design Decisions** always uses sub-bullets with bold labels for each decision point
- **Observation** is a single paragraph — the "so what?" insight
- Never repeat what the code already says — explain *why*, not *what*
- For cells that only display a variable (e.g., `fact_checker_prompt`), the title should be "Inspecting the <object> Structure" and explain what the output reveals
- For smoke-test / sanity-check cells, note exactly what failure modes the test rules out
- For graph compilation cells, include the architecture diagram in ASCII if helpful

### Cohesion Rule — Reforming Existing Markdown Cells

This skill has **full authority to update, reform, and rephrase any existing markdown cell** — including author-written introductory, transitional, and explanatory cells — to ensure the notebook reads as a single cohesive document, not a collection of disconnected pieces.

**What "cohesive" means in practice:**
- A reader opening the notebook cold should feel the narrative pull them forward: problem → setup → implementation → insight → conclusion
- Each markdown cell should set up the code cell below it (or summarise the code cell above it) — no orphaned headers
- Transitions between sections should feel deliberate: the end of one section should hint at what comes next
- Terminology must be consistent throughout — if the intro calls it "fan-out/fan-in", every subsequent cell uses the same phrase
- The business problem stated in the introduction must echo through the notebook and be closed out explicitly in the final cells

**What the skill may do to existing markdown cells:**

| Action | Permitted | Constraint |
|---|---|---|
| Rephrase for clarity and flow | ✅ Yes | Must preserve the original meaning — only the expression changes |
| Reorder bullets or paragraphs within a cell | ✅ Yes | Only if reordering improves logical flow |
| Add a transition sentence at the end of a cell | ✅ Yes | Must bridge to the code cell or section below |
| Add a one-line context sentence at the start of a cell | ✅ Yes | Must connect to what came before |
| Change heading level (e.g., `####` → `##`) | ✅ Yes | Only to align with the notebook's heading hierarchy |
| Consolidate two redundant intro cells into one | ✅ Yes | Must preserve all content — nothing dropped |
| Remove content the author wrote | ❌ No | Never delete author-written explanations or decisions |
| Change the meaning of a design decision | ❌ No | Rephrase expression only, not intent |
| Remove an empty placeholder markdown cell | ✅ Yes | Only if it adds no structural value |

**Reform triggers — reform a markdown cell when:**
1. It uses different terminology for the same concept than surrounding cells
2. It ends abruptly with no transition to the next section
3. It repeats content already covered in the code annotation below it
4. Its heading doesn't match the content of the code cell it introduces
5. It reads as an isolated fragment — no connection to what came before or after
6. It is empty or contains only a placeholder comment

### Special Rule A — Final Output Cell

The last code cell that produces the graph's final output (the `app.invoke(...)` call or equivalent) gets an **extended** annotation. In addition to the standard Input/Output/Design Decisions/Observation structure, append two extra sections:

```markdown
**Business Problem Solved:**
> **The problem:** <restate the business problem from the notebook's introduction — 1 sentence, specific: name the failure mode of the naive approach>
> **How this output proves it's solved:** <connect the actual output fields to the problem — e.g., "The `final_decision.decision = 'Request Revisions'` means three independent critics flagged issues a single reviewer would have missed">
> **The key evidence in the output:** <point to a specific field, value, or timing number that demonstrates the pattern worked>

**Pattern Applicability:**

| Where it thrives | Where it fails |
|---|---|
| <concrete use case where the pattern shines — be specific, not generic> | <concrete failure mode — what breaks, why, under what condition> |
| <second use case> | <second failure mode> |
| <third use case> | <third failure mode> |
```

Rules for this section:
- "The problem" must match the exact Business Problem Statement from the notebook introduction — not a generic description
- "How this output proves it's solved" must reference actual output values from the cell's output, not hypothetical ones
- The thrives/fails table must have at least 3 rows
- Failure modes must be honest and specific: "fails when all agents share the same base model because diversity collapses" not "may not work in all cases"
- This section only appears on the final `invoke` / execution cell — not on every cell

### Special Rule B — End-of-Notebook Section

After all code cells are annotated, append one final standalone markdown cell at the very end of the notebook (after the last existing cell). This is not tied to any code cell — it is a standalone pattern analysis:

```markdown
## Pattern Analysis — Agent Assembly Line (replace with actual pillar name)

### Where This Pattern Thrives

1. **<Use case name>:** <2-sentence explanation of why this pattern is uniquely suited — what property of the pattern matches the property of the problem>
2. **<Use case name>:** <explanation>
3. **<Use case name>:** <explanation>

### Where This Pattern Fails

1. **<Failure condition>:** <why it breaks — be mechanistic, not vague. Name the specific component that degrades>
2. **<Failure condition>:** <explanation>
3. **<Failure condition>:** <explanation>

### The Pattern in One Sentence

> <A precise, reusable mental model. Should complete the sentence: "Use this pattern when you need to...">

### Signals That You Need This Pattern

- <Observable symptom in your system that indicates this pattern would help>
- <Second signal>
- <Third signal>

### Signals That You Don't Need This Pattern

- <Observable symptom that suggests a simpler approach is sufficient>
- <Second signal>
```

Rules for this section:
- Thrives/Fails must each have at least 3 items
- Every failure mode must name the specific mechanism that breaks (not "it doesn't scale" but "the judge node becomes a bottleneck because it runs sequentially after N parallel workers, so latency scales linearly with N")
- "The Pattern in One Sentence" must be prescriptive ("Use this when..."), not descriptive ("This pattern does...")
- This cell is appended once, at the very end, regardless of how many code cells exist

## Instructions

---

### ⚠️ SAFETY CONTRACT — Read before doing anything else

> **Code cells are immutable. You may ONLY modify the `source` field of `markdown` cells.**

The following fields on code cells must **never change** between reading and writing:
- `source` — the cell's code
- `outputs` — all execution outputs (stdout, stderr, display_data, execute_result, error)
- `execution_count` — the cell's run number
- `id`, `metadata` — cell identity

**This is enforced by a mandatory Python verification block in Step 5.** If the assertion fails, the write is aborted and you must diagnose the issue before retrying.

Additionally: **never base an annotation on assumed or stale output.** Always read the actual `outputs` field of the cell you are annotating. If `execution_count` is `None`, the cell has never been run — say so in the annotation. If the cell was just re-run by the user and outputs changed, reload the file before writing.

---

### 1. Identify the target notebook

Parse $ARGUMENTS for a notebook path or module name. If not provided, ask the user which notebook to annotate.

Examples:
- `parallel_tool_use` → annotates `parallel_tool_use/parallel_tool_use.ipynb`
- `hierarchical_agent_teams/hierarchical_agents.ipynb` → direct path

### 2. Read the notebook — full raw JSON

**Do not use the Read tool's parsed view for planning.** Use a Bash command to read the raw JSON so you see the exact cell structure Python will operate on:

```bash
python -c "
import json
with open(r'<NOTEBOOK_PATH>', 'r', encoding='utf-8') as f:
    nb = json.load(f)
print(f'Total cells: {len(nb[\"cells\"])}')
for i, c in enumerate(nb['cells']):
    cid = c.get('id', f'no-id-{i}')
    outs = len(c.get('outputs', []))
    src_len = len(''.join(c.get('source', [])))
    first = ''.join(c.get('source', []))[:60].replace('\n',' ')
    print(f'[{i:02d}] {c[\"cell_type\"]:8s} | id={cid} | exec={c.get(\"execution_count\")} | {outs}out | src={src_len} | {first}')
"
```

Record before proceeding:
- **Total cell count** — compare against this after writing to catch accidental additions/deletions
- **Execution state per code cell** — `execution_count=None` means never run; do not invent outputs for these cells
- **Output counts per code cell** — `0 outputs` is normal for definition cells; `N outputs` means the cell produced visible output; read those outputs before annotating

For each code cell with outputs, read them explicitly:

```bash
python -c "
import json, sys
sys.stdout.reconfigure(encoding='utf-8')
with open(r'<NOTEBOOK_PATH>', 'r', encoding='utf-8') as f:
    nb = json.load(f)
c = nb['cells'][<INDEX>]
for j, out in enumerate(c.get('outputs', [])):
    ot = out.get('output_type')
    if ot == 'stream':
        print(f'[{j}] stream:', repr(''.join(out.get('text', []))[:400]))
    elif ot in ('display_data', 'execute_result'):
        for mime, val in out.get('data', {}).items():
            v = val if isinstance(val, str) else ''.join(val)
            print(f'[{j}] {ot} {mime}:', repr(v[:200]))
    elif ot == 'error':
        print(f'[{j}] ERROR:', out.get('ename'), out.get('evalue'))
"
```

Build a mental model of:
- The business problem stated in the introduction
- The narrative arc the author intended
- The actual execution state (which cells ran, what they produced, what errors occurred)
- Where the flow breaks or feels disconnected

### 3. Plan — Two passes

**Pass 1: Annotation Pass** (code cell coverage)

Walk through cells in order. For each `code` cell:
- Check if the **immediately following cell** is already a markdown annotation (starts with `##` and contains `**Input:**`)
- If yes → decide whether to **update** it (code changed, outputs changed, or annotation is weak/stale) or **skip** it
- If no → `INSERT` a new annotation after it

**Staleness check for existing annotations:** An existing annotation is stale if:
- It references a bug or error that is no longer present in the current cell source or outputs
- It says "incomplete" or "pending" but the cell now has a complete implementation
- It describes outputs that don't match the current `outputs` field

Also identify:
- The **final output cell** (`app.invoke(...)` or equivalent) — gets the **Special Rule A** extended annotation
- Whether a standalone **Pattern Analysis** cell exists at the very end — if not, it must be **APPENDED**

**Pass 2: Cohesion Pass** (existing markdown cell review)

Walk through ALL markdown cells (author-written intro, section, transition cells — not annotation cells you just created). For each, apply the reform triggers from the Cohesion Rule. Ask:
- Does this cell's terminology match the rest of the notebook?
- Does it end with a bridge to what comes next?
- Does its heading accurately describe its content?
- Is it redundant with an annotation cell below it?
- Is it empty or a disconnected fragment?

If any trigger applies → mark it `REFORM`.

**Full action list:**
- `INSERT after cell <id>`: new annotation cell needed
- `INSERT after cell <id> [EXTENDED — Special Rule A]`: final output cell with Business Problem + Pattern Applicability
- `UPDATE cell <id>`: existing annotation is stale or weak — rewrite it
- `SKIP cell <id>`: annotation already accurate and matches current outputs
- `REFORM cell <id>`: existing author-written markdown needs rephrasing for cohesion
- `APPEND Pattern Analysis cell`: end-of-notebook standalone section

Report the full plan before making any changes:
> "Found X new annotations to insert, Y annotations to update, Z already correct. Found W existing markdown cells to reform for cohesion. 1 Pattern Analysis cell to append. Proceed?"

### 4. Write

**Annotation cells** (from Pass 1): analyze each code cell's source **and actual outputs**. Write following the reference pattern. Apply Special Rule A to the final output cell.

Key analysis steps per code cell:
- What libraries/modules are imported and why those specifically?
- What does the **actual output** tell us about the system state? (Read `outputs` field — never guess)
- If `execution_count` is `None`: note the cell has not been run; do not describe outputs
- What would break if this cell were skipped or run in a different order?
- What alternative approaches exist and why was this one chosen?
- Is there a timing observation, token count, or execution signal in the actual output worth noting?

**Cohesion reforms** (from Pass 2): for each `REFORM` cell, rewrite its source while:
- Preserving all original meaning and author intent
- Correcting terminology to match the notebook's consistent vocabulary
- Adding a transition sentence at the end that bridges to the next section
- Adjusting heading level to fit the notebook's hierarchy
- Removing redundancy with annotation cells below

Test: after reforming, read the cell aloud in sequence with its neighbours. If the transition feels natural, the reform is correct.

**Pattern Analysis cell** (Special Rule B): append at the very end.

### 5. Update the notebook JSON — via Python script with mandatory safety verification

**Always write changes via a Python script** written to a temp file and executed with `python <file>`. Never edit the notebook JSON directly with the Edit tool — direct edits bypass the safety check.

The script template must include:

```python
import json, copy, hashlib

NOTEBOOK_PATH = r'<path>'

def make_id(seed):
    return hashlib.md5(seed.encode()).hexdigest()[:8]

def src(text):
    """Convert multiline string to ipynb list-of-lines format."""
    lines = text.split('\n')
    result = []
    for j, line in enumerate(lines):
        if j < len(lines) - 1:
            result.append(line + '\n')
        else:
            if line:
                result.append(line)
    return result

def md_cell(text, cell_id):
    return {'cell_type': 'markdown', 'id': cell_id, 'metadata': {}, 'source': src(text)}

with open(NOTEBOOK_PATH, 'r', encoding='utf-8') as f:
    nb = json.load(f)

# Snapshot the original code cells BEFORE any changes
original_code_cells = copy.deepcopy([c for c in nb['cells'] if c['cell_type'] == 'code'])

# --- MAKE ALL CHANGES HERE ---
# (reforms to markdown source, insertions of new markdown cells)
# NEVER touch nb['cells'][i] where cell_type == 'code'

# --- MANDATORY SAFETY VERIFICATION before writing ---
new_code_cells = [c for c in nb['cells'] if c['cell_type'] == 'code']

assert len(original_code_cells) == len(new_code_cells), (
    f"Code cell count changed: {len(original_code_cells)} -> {len(new_code_cells)}"
)
for orig, new_c in zip(original_code_cells, new_code_cells):
    assert orig['source'] == new_c['source'], \
        f"Code cell source modified: {orig.get('id')}"
    assert orig.get('outputs') == new_c.get('outputs'), \
        f"Code cell outputs modified: {orig.get('id')}"
    assert orig.get('execution_count') == new_c.get('execution_count'), \
        f"Code cell execution_count modified: {orig.get('id')}"

print("Safety check PASSED — all code cells preserved intact.")

with open(NOTEBOOK_PATH, 'w', encoding='utf-8') as f:
    json.dump(nb, f, ensure_ascii=False, indent=1)

print(f"Done. Final cell count: {len(nb['cells'])}")
```

**For new annotation cells (Insert):** build using `md_cell(text, make_id("unique_seed"))`.

**For reformed markdown cells (Reform):** update `cells[idx]['source'] = src(new_text)` — the cell `id` stays the same, only `source` changes.

**For the final output cell (Special Rule A):** append `**Business Problem Solved:**` and `**Pattern Applicability:**` blocks after `**Observation:**` in the same annotation cell.

**For the Pattern Analysis cell (Special Rule B):** append a new `md_cell(...)` after the last existing cell in the new cells list.

**After the script runs:** verify the final cell count matches `original_count + inserted_count` and print the delta to the user.

### 6. Report

Tell the user:
- How many new annotation cells were inserted
- How many existing annotation cells were updated (and why they were stale)
- How many annotation cells were already correct and skipped
- How many author-written markdown cells were reformed for cohesion (list their approximate position or heading so the user can review)
- Whether the Business Problem / Pattern Applicability section was added to the final output cell
- Whether the Pattern Analysis end-of-notebook cell was appended
- Any code cells that were ambiguous and may need manual review
- The **before → after cell count** (e.g., "27 → 34 cells")
- A one-sentence assessment: "The notebook now reads as [X] — [brief description of the narrative arc]"
