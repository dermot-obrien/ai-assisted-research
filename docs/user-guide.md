# RMS User Guide: Step-by-Step Instructions

This guide provides instructions for both human researchers and AI agents using the Research Management System.

---

## 0. Initializing in an Existing Repository

If you are adding the Research Management System to a pre-existing workspace, use the **Discovery** agent to reconstruct the lineage of ideas.

### Step 0.1: Run Workspace Discovery
The Discovery agent scans your code, docs, and git history to identify your starting nodes.
```bash
python tools/discovery.py
```

### Step 0.2: Confirmation Dialogue
The agent will propose a root node (H-000) and a current implementing node (H-001). Confirm the reconstruction to initialize the `docs/research/hypothesis-dag.yaml`.

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
Create `docs/research/hypothesis-dag.yaml` in the root of your research sub-module.
- **Node H-000**: represent the external SOTA.
- **Setup Metadata**: Include the `standardized_setup` paths for data and benchmarks in the project metadata.

---

## 2. Proposing New Avenues

The **Specialist** agent brainstorms new variants to explore.

### Step 2.1: Update the DAG
Use the `dag_update.py` tool to propose new nodes.
```bash
python tools/dag_update.py --action add --parent H-001 --hypothesis "New Variant Description" --target 0.05
```

---

## 3. Executing Research (The Worker Loop)

The **Worker** agent performs the actual research, implementation, and benchmarking.

### Step 3.1: Claim a Node
Find a `pending` node in the DAG and initialize the research branch.
```bash
python tools/branch_manager.py --action init --node-id H-001 --topic "Topic-Name" --agent-id "Agent-Name" --parent-perf 0.90 --target-imp 0.05
```

### Step 3.2: Implement & Benchmark
- Perform code changes in the enclosing workspace.
- Run your project's benchmark suite.
- Record the `actual_performance` in `docs/research/H-{ID}/metadata.yaml`.

### Step 3.3: Synthesis
Use the templates in `templates/` to generate your research outputs in `docs/research/H-{ID}/`.
- `blog_template.md` -> `docs/research/H-{ID}/{node_id}-blog.md`
- `arxiv_template.md` -> `docs/research/H-{ID}/{node_id}-arxiv.md`

### Step 3.4: Handoff
Hand off the strand to the Auditor.
```bash
python tools/branch_manager.py --action handoff --node-id H-001 --next-role auditor --instructions "Ready for verification." --performance 0.95
```

---

## 4. Verification and Integration

The **Auditor** agent and **Human Reviewer** finalize the research.

### Step 4.1: Run Audit
The Auditor verifies the results.
```bash
python tools/audit_verify.py --action verify
```

### Step 4.2: Human Review (Gate 3)
The Human reviewer checks the Blog, ARXIV paper, and code changes.

### Step 4.3: Merge to Main
Once approved, the research branch is merged into `main`, and the `hypothesis-dag.yaml` is updated to `completed`.

---

## Summary of Agent Tools

| Tool | Role | Purpose |
| :--- | :--- | :--- |
| `sota_baseline.py` | Specialist | Discovery of SOTA and baseline extraction. |
| `dag_update.py` | Specialist | Adding/updating nodes in the central DAG. |
| `branch_manager.py` | Worker | Branch creation and metadata-driven handoffs. |
| `audit_verify.py` | Auditor | Automated verification of performance and deliverables. |
