# Deliverable: WI-001-D01 Framework Design & Schema

> Activity: WI-001-A1 Framework Design & Schema
> Status: Complete (Refactored for v1.1.0)

## Overview

This deliverable defines the core schemas and conventions for the Research Management System, focusing on the "Hypothesis DAG" and multi-agent coordination via the split Design/Execution architecture.

## 1. Hypothesis DAG Schema (`hypothesis-dag.yaml`)

The `hypothesis-dag.yaml` file resides in the repository root and acts as the centralized map of the research search space.

### Schema Definition

```yaml
# hypothesis-dag.yaml

project:
  name: "{Project Name}"
  objective: "{Primary research objective}"
  primary_metric: "{e.g., MSE, Accuracy}"
  sota_baseline:
    external_best_performance: {value}
    source: "{URL to SOTA paper}"
    dataset: "{Link to benchmark dataset}"

nodes:
  - id: H-000  # The Root (Baseline)
    hypothesis: "{Core project hypothesis}"
    status: validated
    performance: {value}
    avenues: [H-001, H-002]
    
  - id: H-001
    parent: H-000
    hypothesis: "{Variant/Avenue hypothesis}"
    status: pending  # pending | framed | in_progress | validated | ineffective | discarded
    target_improvement: {value}
    actual_performance: null
    work_item_id: WI-NNN  # Linked AAW Work Item
    branch: null
    deliverables:
      blog: null
      arxiv: null
      pivot: null
    notes: []
```

### Node Status Definitions

- **pending**: A proposed idea with no experimental design yet.
- **framed**: Experimental design complete (AAW Work Item created with scope and plan).
- **in_progress**: Implementation active (Git research branch created).
- **validated**: Research finished; performance improved upon parent/SOTA.
- **ineffective**: Research finished; performance did not meet the target.
- **discarded**: Research stopped early or deprecated.

## 2. Work-Item Metadata Schema (`metadata.yaml`)

Each research strand (stored in `change/work-items/`) contains a `metadata.yaml` to track its local state.

### Schema Definition

```yaml
# metadata.yaml

node_id: H-001
branch_name: research/H-001-gnn-drug-discovery
status: in_progress  # in_progress | awaiting_review | done

current_owner:
  id: "Agent-007"
  session_id: "S-456"
  role: "worker"

parent_performance: 0.92
target_improvement: 0.02
actual_performance: null

handoff:
  next_role: "auditor"
  instructions: "Implementation complete. Ready for clean-room verification."
  timestamp: "2026-03-01T09:10:00Z"

milestones:
  - id: baseline
    status: completed
  - id: implementation
    status: in_progress
  - id: benchmarking
    status: pending
  - id: synthesis
    status: pending
```

## 3. Git Branching & Handoff Conventions

### Branching Strategy

- **Main Branch (`main`)**: Contains the `hypothesis-dag.yaml` and verified deliverables.
- **Research Branches (`research/H-{ID}-{topic}`)**: Created only when a hypothesis moves from `framed` to `in_progress`.

### The Core Loop (Process Integrity)

1. **Design (The Blueprint)**:
   - Command: `/start-hypothesis {node_id}`
   - Action: Delegates to AAW `/start-work`.
   - Result: Node status moves to **`framed`**.

2. **Execution (The Implementation)**:
   - Command: `/progress-hypothesis {WI_id} {node_id}`
   - Action: Creates Git branch and delegates to AAW `/progress-work`.
   - Result: Node status moves to **`in_progress`**.

3. **Homecoming (The Synchronization)**:
   - Command: `/sync-research-result {node_id} {WI_id}`
   - Action: Reconciles AAW metrics/findings with the DAG.
   - Result: Node status moves to **`validated`** or **`ineffective`**.
