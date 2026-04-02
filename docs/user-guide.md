# RMS User Guide: Step-by-Step Instructions

This guide provides instructions for both human researchers and AI agents using the Research Management System. All research execution follows the unified hierarchy within the **AI-Assisted Work (AAW)** framework.

---

## 0. Initializing in an Existing Repository

If you are adding the Research Management System to a pre-existing workspace, use the **Discovery** agent to reconstruct the lineage of ideas.

### Step 0.1: Run Workspace Discovery
The Discovery agent scans your code, docs, and git history to identify your starting nodes.
```bash
python tools/discovery.py
```

### Step 0.2: Confirmation Dialogue
The agent will propose a root node (H-000) and a current implementing node (H-001). Confirm the reconstruction to initialize the `hypothesis-dag.yaml` (typically in the root or `docs/`).

---

## 1. Initializing a New Research Project

To start a new research project, the **Specialist** agent (or Human) must establish the SOTA baseline.

### Step 1.1: Run SOTA Discovery
Use the `sota_baseline.py` tool to find the current best performance for your topic.
```bash
python tools/sota_baseline.py --query "Your Topic" --output baseline.yaml
```

### Step 1.2: Mandatory Benchmark & Data Setup
Before initializing the DAG, the **Specialist** (or Human) MUST establish the standardized testing environment:
1.  **Identify Dataset**: Place research data in `performance/data/{project_name}/`.
2.  **Supply Benchmark Script**: Place the primary evaluation code in `performance/benchmarks/evaluate_{metric}.py`.
3.  **Validate Baseline**: Run the benchmark script against the root code to ensure it matches the reported SOTA performance (Node H-000).

### Step 1.3: Initialize the DAG
Create `hypothesis-dag.yaml` in the repository root.
- **Node H-000**: Represents the external SOTA.
- **Setup Metadata**: Include the `primary_metric` and `standardized_setup` paths.

---

## 2. Proposing & Framing Avenues

The **Specialist** agent brainstorms new variants and creates the blueprint for exploration.

### Step 2.1: Update the DAG
Use the `dag_update.py` tool to propose new nodes.
```bash
python tools/dag_update.py --action add --parent H-001 --hypothesis "New Variant Description" --target 0.05
```

### Step 2.2: Start the Hypothesis (Design Phase)
Design the scope and plan for a hypothesis without necessarily starting implementation.
```bash
/start-hypothesis {node_id}
```
- **Action**: Delegates to AAW `/start-work` to create a new research work item.
- **Action**: Populates `scope.md`, `research.md`, and `plan.md`.
- **Status Change**: DAG node status moves from `pending` to **`framed`**.

---

## 3. Executing Research (Execution Phase)

The **Worker** agent activates a framed item and performs the implementation.

### Step 3.1: Progress the Hypothesis (Activation & Execution)
Activate a framed item or continue execution of tasks.
```bash
/progress-hypothesis {WI_id} {node_id}
```
- **First Call**: Creates the Git research branch, initializes `metadata.yaml`, and moves DAG status to **`in_progress`**.
- **Execution Loop**: Delegates to AAW `/progress-work` to execute tasks and record findings.

### Step 3.2: Synthesis
Once implementation is complete, generate outputs in the `deliverables/` folder.
- `blog_template.md` -> `deliverables/{node_id}-blog.md`
- `arxiv_template.md` -> `deliverables/{node_id}-arxiv.md`
- `pivot_template.md` -> `deliverables/{node_id}-pivot.md` (if result is ineffective)

---

## 4. Verification and Synchronization

### Step 4.1: Run Audit
The Auditor verifies the results using the Clean Room check.
```bash
python tools/audit_verify.py --action verify --clean-room
```

### Step 4.2: Synchronize to RMS
Once the AAW work item is `done`, synchronize the result back to the master DAG:
```bash
/sync-research-result {node_id} {WI_id}
```
This closes the loop, updating the DAG status (`validated` or `ineffective`) and linking the deliverables.

### Step 4.3: Merge to Main
The research branch is merged into `main`, and the `hypothesis-dag.yaml` is updated on the main branch.

---

## 5. Experiment Logging (v1.2.0)

After each experiment, record the result in one step:
```bash
/log-experiment {node_id} {metric_name}={value} "{hypothesis}"
```

This automatically:
- Appends to `experiment-log.jsonl`
- Updates the DAG node's `actual_performance`
- Regenerates `node-index.yaml` and the dashboard
- Git commits all changes

For breakthroughs (results that change research direction):
```bash
/log-experiment {node_id} metric=value "hypothesis" --breakthrough "Title"
```
This triggers automatic cascade analysis.

See [`agents/log-experiment.md`](../agents/log-experiment.md) for the full protocol.

---

## 6. Breakthrough Cascade (v1.2.0)

When a breakthrough occurs, analyse its impact on other nodes:
```bash
/cascade {node_id}
```

This is triggered automatically by `/log-experiment --breakthrough` and `/sync-research-result`. It identifies nodes whose assumptions changed and updates priorities.

See [`agents/cascade.md`](../agents/cascade.md) for the full protocol.

---

## 7. Session Management (v1.2.0)

### Starting a Session
```bash
/session-start
```
Shows the dashboard, golden path priorities, recent breakthroughs, and pending cascades. **This should be the first command in every session.**

### Ending a Session
```bash
/session-end
```
Generates a session report YAML, commits it, and provides a handoff summary. **This should be the last command.**

See [`agents/session.md`](../agents/session.md) for the full protocol.

---

## Summary of Agent Tools

| Tool | Role | Purpose |
| :--- | :--- | :--- |
| `sota_baseline.py` | Specialist | Discovery of SOTA and baseline extraction. |
| `dag_update.py` | Specialist | Adding/updating nodes in the central DAG with concurrency locking. |
| `branch_manager.py` | Worker | Manage research branches and metadata (called by /progress-hypothesis). |
| `audit_verify.py` | Auditor | Automated verification with Clean Room support. |
| `/sync-research-result` | Worker | The "Return Path" from AAW back to the RMS DAG. |
| `/log-experiment` | Experiment Logger | One-step experiment recording and DAG sync (v1.2.0). |
| `/cascade` | Cascade Analyst | Breakthrough impact propagation through DAG (v1.2.0). |
| `/session-start` | Session Manager | Research session briefing (v1.2.0). |
| `/session-end` | Session Manager | Session report and handoff (v1.2.0). |
