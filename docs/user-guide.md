# RMS User Guide: Step-by-Step Instructions

This guide provides instructions for both human researchers and AI agents using the Research Management System.

---

## 0. Initializing in an Existing Repository

If you are adding the Research Management System to a pre-existing workspace, use the **Discovery** agent to reconstruct the lineage of ideas and set up the AAW integration.

### Step 0.1: Run Workspace Discovery
The Discovery agent scans your code, docs, and git history to identify your starting nodes.
```bash
python tools/discovery.py
```

### Step 0.2: Create Research Initiative
The Discovery agent creates a research initiative via AAW's `/start-initiative` in the intent repo's `change/initiatives/` directory.

### Step 0.3: Create Root Work Item
The Discovery agent creates a root work item via AAW's `/start-work` in the intent repo's `change/work-items/` directory. Deliverables include:
- `hypothesis-dag.yaml` — the central DAG
- `RESEARCH_PLAN.md` — research scope and objectives
- SOTA documents

### Step 0.4: Create Signpost
The Discovery agent writes `research.yaml` at the workspace root, pointing to the initiative, root work item, DAG path, and work items directory.

### Step 0.5: Confirmation Dialogue
The agent will propose a root node (H-000) and a current implementing node (H-001). Confirm the reconstruction, initiative, and root work item to finalize initialization.

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
Follow the same steps as Section 0 (Steps 0.2–0.4):
- Create research initiative via `/start-initiative`
- Create root work item via `/start-work` with hypothesis-dag.yaml and RESEARCH_PLAN.md as deliverables
- Write `research.yaml` signpost at workspace root

### Step 1.4: Initialize the DAG
Create `hypothesis-dag.yaml` as a deliverable in the root work item (e.g., `deliverables/D01-hypothesis-dag.yaml`).
- **Node H-000**: represents the external SOTA.
- **Setup Metadata**: Include the `standardized_setup` paths for data and benchmarks in the project metadata.

---

## 2. Proposing New Avenues

The **Specialist** agent brainstorms new variants to explore.

### Step 2.1: Read Signpost
Read `research.yaml` from workspace root to locate the DAG in the root work item's deliverables.

### Step 2.2: Update the DAG
Propose new nodes by updating the hypothesis-dag.yaml deliverable in the root work item. New nodes are added with `status: pending` and `work_item_id: null`. Actual work items are created by the Worker when execution begins.

You can use the helper tool if desired:
```bash
python tools/dag_update.py --action add --parent H-001 --hypothesis "New Variant Description" --target 0.05
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
- Update the DAG node's `work_item_id` field with the new work item ID

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

### Step 4.1: Run Audit
The Auditor verifies the results by examining the work item's deliverables:
```bash
python tools/audit_verify.py --action verify
```

### Step 4.2: Human Review (Gate 3)
The Human reviewer checks the Blog, ARXIV paper, and code changes via the work item's deliverables.

### Step 4.3: Merge to Main
Once approved, the work item branch (`wi/WI-{NNN}-...`) is merged, and the `hypothesis-dag.yaml` node is updated to `completed` in the root work item's deliverables.

---

## Summary of Agent Tools

| Tool | Role | Purpose |
| :--- | :--- | :--- |
| `dag_update.py` | Specialist | Adding/updating nodes in the central DAG. |
| `branch_manager.py` | Worker | Branch creation and metadata-driven handoffs. |
| `audit_verify.py` | Auditor | Automated verification of performance and deliverables. |

## Key Artifacts

| Artifact | Location | Purpose |
| :--- | :--- | :--- |
| `research.yaml` | Workspace root | Signpost for O(1) agent discovery of all research paths |
| `hypothesis-dag.yaml` | Root work item deliverables | Central map of the research solution space |
| `RESEARCH_PLAN.md` | Root work item deliverables | Research scope, objectives, questions |
| Per-node work items | Intent repo `change/work-items/` | Individual research strand execution via AAW |
| Initiative | Intent repo `change/initiatives/` | Strategic container grouping all research work items |
