# RMS User Guide: Step-by-Step Instructions

This guide provides instructions for both human researchers and AI agents using the Research Management System.

---

## 0. Initializing in an Existing Repository

If you are adding the Research Management System to a pre-existing workspace, use the **Discovery** agent to reconstruct the lineage of ideas and set up the AAW integration.

### Step 0.1: Check for Existing Signpost
Before starting, check whether `research.yaml` already exists at the workspace root. If it does, the RMS is already initialized — confirm with the user before reinitializing.

### Step 0.2: Run Workspace Discovery
The Discovery agent scans your code, docs, and git history to identify your starting nodes.
```bash
python tools/discovery.py
```

### Step 0.3: Scan for Existing Research Documentation
Search the workspace for existing hypothesis trees, research notes, experiment logs, and prior analysis. These will be merged into the structured DAG in Step 0.7 — nothing should be lost.

### Step 0.4: Baseline the SOTA
The Discovery agent performs comprehensive online research to establish the current state-of-the-art:
1. **Identify** the External Best Performance (EBP) and top models across all relevant domains
2. **Identify** the most authoritative datasets and benchmarks used by the community
3. **Identify** standard evaluation metrics and what constitutes "beating SOTA"
4. **Identify** gaps and opportunities where the project's approach differentiates
5. **Produce** a **research landscape document** (`SOTA_research_landscape.md`) covering the full scope:
   - All research domains and cross-cutting themes
   - Performance tables with specific numbers per domain
   - Authoritative benchmarks and datasets with descriptions
   - Key papers to cite (with venues and years)
   - Competitive landscape and strategic positioning
   - Direct links to sources
   - Analysis of gaps and opportunities
6. **Optionally produce** per-domain deep-dive documents (`SOTA_{domain}.md`) for domains requiring detailed treatment (extensive benchmark tables, algorithm comparisons, dataset catalogues)

### Step 0.5: Create Research Initiative
The Discovery agent creates a research initiative via AAW's `/start-initiative` in the intent repo's `change/initiatives/` directory.

### Step 0.6: Create Root Work Item
The Discovery agent creates a root work item via AAW's `/start-work` in the intent repo's `change/work-items/` directory. Deliverables follow the `DNN-name` convention:
- `D01-hypothesis-dag.yaml` — the central DAG
- `D02-research-plan.md` — research scope and objectives
- `D03-sota-research-landscape.md` — overall research landscape covering full scope
- `D04-sota-{domain}.md` onwards — optional per-domain deep dives for detailed treatment

### Step 0.7: Build the Hypothesis DAG
Create `D01-hypothesis-dag.yaml` in the root work item's deliverables. **Merge all existing research documentation** found in Step 0.3 into the structured DAG — every hypothesis, finding, parameter sweep, code reference, and evidence string must be preserved. See the Discovery agent definition for the node schema and category convention.

### Step 0.8: Create Signpost
The Discovery agent writes `research.yaml` at the workspace root, pointing to the initiative, root work item, DAG path, and work items directory.

### Step 0.9: Backfill Existing Work Items
If pre-existing work items relate to the research (e.g., from prior development), update their `progress.yaml` to set `initiative_id` to the new initiative ID. This groups them under the initiative. Also set the `work_item_id` field on the corresponding DAG nodes.

### Step 0.10: Trigger Visuals
Invoke `/housekeep` to generate the initial DAG visuals (SVG + PNG + Mermaid).

### Step 0.11: Confirmation Dialogue
The agent will propose a root node (H-000), derived hypothesis nodes, SOTA baselines, and the full research plan. Confirm the reconstruction, initiative, and root work item to finalize initialization.

---

## 1. Initializing a New Research Project

To start a new research project, the **Specialist** agent (or Human) must establish the SOTA baseline.

### Step 1.1: Run SOTA Discovery
The Specialist agent performs comprehensive online research (web search, ArXiv, leaderboards) to find the current best performance for your topic. Identify the External Best Performance (EBP) and primary metrics.

### Step 1.2: Mandatory Benchmark & Data Setup
Before initializing the DAG, the **Specialist** (or Human) MUST establish the standardized testing environment:
1.  **Identify Dataset**: Place research data in `performance/data/{project_name}/`.
2.  **Supply Benchmark Script**: Place the primary evaluation code in `performance/benchmarks/evaluate_{metric}.py`.
3.  **Validate Baseline**: Run the benchmark script against the root code to ensure it matches the reported SOTA performance (Node H-000).

### Step 1.3: Create Initiative and Root Work Item
Follow the same steps as Section 0 (Steps 0.5–0.6):
- Create research initiative via `/start-initiative`
- Create root work item via `/start-work` with deliverables using `DNN-name` convention
- Write `research.yaml` signpost at workspace root

### Step 1.4: Initialize the DAG
Create `D01-hypothesis-dag.yaml` as a deliverable in the root work item.
- **Node H-000**: represents the external SOTA.
- **Setup Metadata**: Include the `standardized_setup` paths for data and benchmarks in the project metadata.

---

## 1.5. Establishing Baselines (Mandatory Before Hypothesis Execution)

Before any hypothesis node can move to `in_progress`, the domain MUST have validated baselines. This is enforced by Principle 6 (Baseline Anchoring).

### Step 1.5.1: Select SOTA Model
For each domain category (H-1xx Anomaly, H-2xx Forecasting, H-3xx Pattern Recognition), the Specialist selects a reproducible SOTA model:
- Must be the current or recent top performer on the chosen benchmark
- Must have open-source code or a reproducible reference implementation
- Must run on the standardized dataset identified in SOTA research

### Step 1.5.2: Create Baseline Node in DAG
Add a baseline node as a child of the domain category head (H-100, H-200, etc.) with:
- `hypothesis`: "Reproduce {model} on {dataset} — establishes EBP for {domain}"
- `target_improvement`: null (this IS the baseline, not an improvement)
- Special field: `baseline: true` (marks this as a reference point, not a hypothesis)

### Step 1.5.3: Execute Baseline via Worker
The Worker creates a work item and runs the baseline:
1. Download/prepare the standardized dataset
2. Run the SOTA model with published hyperparameters
3. Record `actual_performance` metrics (MSE, MAE, AUROC, etc.)
4. Verify results match published numbers (within tolerance)

### Step 1.5.4: Three-Stage Comparison
Once the regular-TS baseline is established, the Worker (or Specialist) creates two companion baseline nodes:
- **SOTA on irregular TS**: Same model, but data converted to irregular intervals (random subsampling, gap injection, or natural irregular source)
- **GIFS on irregular TS**: Our pipeline on the same irregular data

This produces the normalization triple:

| Stage | What it shows |
|-------|---------------|
| SOTA on regular TS | The ceiling — best known performance |
| SOTA on irregular TS | The degradation — how much regularity assumptions cost |
| GIFS on irregular TS | Our contribution — how GIFS closes the gap |

### Step 1.5.5: Record in DAG
All three baseline nodes must reach `status: validated` before domain hypothesis nodes can proceed. The Auditor verifies baseline reproducibility.

---

## 2. Proposing New Avenues

The **Specialist** agent brainstorms new variants to explore.

### Step 2.1: Read Signpost
Read `research.yaml` from workspace root to locate the DAG in the root work item's deliverables.

### Step 2.2: Update the DAG
Propose new nodes by updating the hypothesis-dag.yaml deliverable in the root work item. New nodes are added with `status: pending` and `work_item_id: null`. Actual work items are created by the Worker when execution begins. See the Discovery agent definition for the node schema and H-xxx category convention.

You can use the helper tool if desired:
```bash
python tools/dag_update.py --action add --parent H-001 --hypothesis "New Variant Description" --target 0.05
```

### Step 2.3: Update the Visual
After modifying the DAG, invoke `/housekeep` to regenerate all visual representations in the root work item's deliverables:
- **`DAG-visual.svg`** + **`DAG-visual.png`** — generated by `tools/dag_visual.py` (radial sector layout)
- **`DAG-visual.md`** — supplementary Mermaid tree view

The tool generates both outputs in a single run:
```bash
python tools/dag_visual.py [dag_yaml_path] [output_dir]
```

---

## 3. Executing Research (The Worker Loop)

The **Worker** agent performs the actual research, implementation, and benchmarking.

### Step 3.1: Read Signpost and DAG
Read `research.yaml` to find the DAG path. Load hypothesis-dag.yaml and find a `pending` node.

### Step 3.2: Create AAW Work Item
Use AAW's `/start-work` to create a work item for the node:
- **Title**: "Research {node_id} - {hypothesis_summary}"
- **Location**: The work items path from research.yaml
- Set `initiative_id` to the research initiative ID in the work item's progress.yaml
- Add `research_node: {node_id}` to progress.yaml metadata
- **Immediately** update the DAG node: set `work_item_id` to the new work item ID and `status` to `in_progress`

### Step 3.3: Implement & Benchmark
Use `/progress-work WI-{NNN}` for all execution:
- Perform code changes in the enclosing workspace
- Run your project's benchmark suite
- Record the `actual_performance` in the DAG node (in root work item deliverables)

### Step 3.4: Synthesis
Generate research outputs as AAW deliverables within the work item:
- Blog narrative (using `templates/blog_template.md`)
- ARXIV paper (using `templates/arxiv_template.md`)
- Changes log

### Step 3.5: Handoff
Hand off the strand to the Auditor. The work item's AAW activity model handles the transition — the Auditor picks up a verification activity within the same work item or a separate audit work item.

---

## 4. Verification and Integration

The **Auditor** agent and **Human Reviewer** finalize the research.

### Step 4.1: Read Signpost and DAG
The Auditor reads `research.yaml` to find the DAG and locates the node(s) to audit via their `work_item_id`.

### Step 4.2: Run Audit
The Auditor picks up a verification activity within the work item (or creates a separate audit work item) and verifies:
- Re-run benchmark suites to confirm `actual_performance` values
- Verify code changes are non-destructive and artifact-free
- Confirm consistency between data, DAG claims, and deliverable reports
- Check that DAG `status` is appropriate (validated/ineffective, not blanket completed)

```bash
python tools/audit_verify.py --action verify
```

### Step 4.3: Human Review (Gate 3)
The Human reviewer checks the Blog, ARXIV paper, and code changes via the work item's deliverables.

### Step 4.4: Merge to Main
Once approved, the work item branch (`wi/WI-{NNN}-...`) is merged, and the `hypothesis-dag.yaml` node status is confirmed in the root work item's deliverables.

---

## Deliverable Naming Convention

Root work item deliverables use the `DNN-name` convention:

| ID | Name | Purpose |
|----|------|---------|
| D01 | `D01-hypothesis-dag.yaml` | Central DAG |
| D02 | `D02-research-plan.md` | Research scope and objectives |
| D03 | `D03-sota-research-landscape.md` | Overall SOTA landscape |
| D04+ | `D04-sota-{domain}.md` | Per-domain SOTA deep dives |

Per-node work item deliverables are numbered independently within their work item.

---

## Summary of Agent Tools

| Tool | Role | Purpose |
| :--- | :--- | :--- |
| `dag_update.py` | Specialist | Adding/updating nodes in the central DAG. |
| `dag_visual.py` | Housekeeper | Generating radial SVG + PNG visualization of the DAG. |
| `branch_manager.py` | Worker | Branch creation and metadata-driven handoffs. |
| `audit_verify.py` | Auditor | Automated verification of performance and deliverables. |

## Key Artifacts

| Artifact | Location | Purpose |
| :--- | :--- | :--- |
| `research.yaml` | Workspace root | Signpost for O(1) agent discovery of all research paths |
| `hypothesis-dag.yaml` | Root work item deliverables | Central map of the research solution space |
| `DAG-visual.svg` | Root work item deliverables | Radial SVG of the DAG (vector, regenerated by Housekeeper) |
| `DAG-visual.png` | Root work item deliverables | Radial PNG of the DAG (raster, converted from SVG via cairosvg) |
| `DAG-visual.md` | Root work item deliverables | Mermaid diagram of the DAG (supplementary) |
| `RESEARCH_PLAN.md` | Root work item deliverables | Research scope, objectives, questions |
| Per-node work items | Intent repo `change/work-items/` | Individual research strand execution via AAW |
| Initiative | Intent repo `change/initiatives/` | Strategic container grouping all research work items |
