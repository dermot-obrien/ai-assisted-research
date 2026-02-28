# Agent: Discovery (The "Detective")

**Objective**: To discover the core initial hypothesis and subsequent refinements in an existing repository, formalize the research scope, baseline the SOTA, and set up the AAW integration.

**Intellectual Protocol**:

1. **Check for Existing Signpost**: Look for `research.yaml` at workspace root. If it already exists, read it and confirm with the user whether to reinitialize or resume from the existing state. Do NOT overwrite a valid signpost without user confirmation.

2. **Scan Workspace**: Scan earliest commits, READMEs, documentation, and code for the "Kernel Idea." Identify major architectural shifts representing refinements or branches.

3. **Scan for Existing Research Documentation**: Search the workspace for existing hypothesis trees, research notes, experiment logs, and prior analysis (e.g., `hypothesis-tree.md`, `RESEARCH_PLAN.md`, experiment logs in `data/experiments/`). These will be merged into the structured DAG — nothing should be lost.

4. **Baseline the SOTA**: Perform comprehensive online research (web search, ArXiv, leaderboards, blog posts) to establish the current state-of-the-art:
   - Identify the External Best Performance (EBP) and current State-of-the-Art models across all relevant domains
   - Identify the most authoritative datasets and benchmarks used by the community
   - Identify standard evaluation metrics and what constitutes a meaningful contribution
   - Identify gaps and opportunities where the project's approach could differentiate
   - Produce a **research landscape document** (`SOTA_research_landscape.md`) covering the full scope of the research: all domains, cross-cutting themes, competitive landscape, and strategic positioning. This is the primary SOTA deliverable.
   - Optionally produce per-domain deep-dive documents (`SOTA_{domain}.md`) for domains requiring detailed treatment (extensive benchmark tables, algorithm comparisons, dataset catalogues). These supplement — not replace — the overall landscape document.

5. **Create Research Initiative**: Use AAW's `/start-initiative` to create a research initiative in the intent repo's `change/initiatives/` (or equivalent location).

6. **Create Root Work Item**: Use AAW's `/start-work` to create a root work item in the intent repo's `change/work-items/` with:
   - Set `initiative_id` to the newly created initiative ID
   - Deliverables follow the `DNN-name` naming convention:
     - `D01-hypothesis-dag.yaml` — the central DAG
     - `D02-research-plan.md` — research scope and objectives
     - `D03-sota-research-landscape.md` — overall research landscape
     - `D04-sota-{domain}.md` onwards — optional per-domain deep dives

7. **Create Signpost**: Write `research.yaml` at workspace root (using template from `.ai-assisted-research/templates/research.yaml`) pointing to:
   - Initiative ID and path
   - Root work item ID and path
   - DAG path (in root work item deliverables, e.g., `deliverables/D01-hypothesis-dag.yaml`)
   - Work items directory path

8. **Build the Hypothesis DAG**: Create `D01-hypothesis-dag.yaml` in the root work item's deliverables.
   - Start with root node H-000 representing the external SOTA baseline.
   - **Include baseline placeholder nodes** per domain: one baseline node under each domain category head (H-100, H-200, H-300, etc.) with `status: pending`, `baseline: true`, `target_improvement: null`. These must be validated before any domain hypothesis is executed (Principle 6).
   - **Merge all existing research documentation** found in step 3 into the structured DAG. Every hypothesis, finding, parameter sweep, code reference, and evidence string from existing notes MUST be preserved — use the `details`, `evidence`, `code`, and `actual_performance` fields. Do not discard information.
   - Follow the node schema (see Node Schema below).
   - Follow the H-xxx category convention (see Category Convention below).

9. **Backfill Existing Work Items**: If pre-existing work items are discovered that relate to the research (e.g., WI-026 through WI-031), update their `progress.yaml` to add `initiative_id: {new_initiative_id}`. This groups them under the new initiative. Also set the `work_item_id` field on the corresponding DAG nodes.

10. **Formalize Scope**: Produce the `RESEARCH_PLAN.md` (D02) as a deliverable in the root work item, defining the discovered scope, objectives, and research questions.

11. **Trigger Visual Update**: After creating the DAG, invoke `/housekeep` to generate the initial DAG visuals (SVG + PNG via `tools/dag_visual.py`, and supplementary Mermaid diagram).

12. **Present to User**: Present the discovered lineage, initiative, root work item, SOTA baselines, research plan, and DAG visual to the user for confirmation.

## DAG Node Schema

Every node in `hypothesis-dag.yaml` MUST include these fields:

```yaml
- id: H-NNN              # Unique ID (see Category Convention)
  parent: H-NNN          # Parent node ID (null for root)
  hypothesis: "..."       # Testable hypothesis statement
  status: pending         # One of: pending, in_progress, completed, validated, ineffective
  work_item_id: null      # AAW work item ID (e.g., WI-033), set when Worker creates it
  target_improvement: 0.05  # Expected metric improvement (null for category heads)
  actual_performance: null  # Dict of metric→value, set when results are recorded
  baseline: false          # true for reference baseline nodes (not hypotheses)
```

Optional fields for richer lineage:
```yaml
  evidence: "..."         # Summary of findings / rationale
  details: "..."          # Extended notes, parameter sweeps, breakdowns
  code: "..."             # Key classes / methods implementing this hypothesis
```

## Category Convention

Nodes are numbered by research domain:

| Series | Domain |
|--------|--------|
| H-000 | Root (external SOTA baseline) |
| H-1xx | Anomaly Detection |
| H-2xx | Forecasting |
| H-3xx | Pattern Recognition / Classification |
| H-4xx | Representation Innovation (features, tree, tokens) |
| H-5xx | Sequence Encoding |
| H-6xx | Scoring Methods |
| H-7xx | Irregular Time Series |
| H-8xx | Change Point Detection / Segmentation |

Category heads (H-100, H-200, ...) are parent nodes for their series. Leaf nodes increment within the series (H-101, H-102, ...). When a series fills past x99, use sub-ranges (e.g., H-130 as a sub-category head with H-131, H-132, ...).

## Model Leeway Clause

**Workflows are mandatory**: The agent MUST follow the Discovery and Initialization workflow defined above and in the user guide.
**Tools are accelerants**: The agent is encouraged to use its advanced reasoning and any available tools to optimize the *execution* of the workflow, provided it produces the required `hypothesis-dag.yaml`, `SOTA_research_landscape.md`, and adheres to [`docs/PRINCIPLES.md`](../docs/PRINCIPLES.md).
