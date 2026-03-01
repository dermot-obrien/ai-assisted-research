# Deliverable: WI-001-D01 Framework Design & Schema

> Activity: WI-001-A1 Framework Design & Schema
> Status: Complete

## Overview

This deliverable defines the core schemas and conventions for the Research Management System, focusing on the "Hypothesis DAG" and multi-agent coordination.

## 1. Hypothesis DAG Schema (`hypothesis-dag.yaml`)

The `hypothesis-dag.yaml` file resides in the root of the research sub-module and acts as the centralized map of the search space.

### Schema Definition

```yaml
# hypothesis-dag.yaml

project:
  name: "{Project Name}"
  objective: "{Primary research objective}"
  sota_baseline:
    external_best_performance: {value}
    metric: "{e.g., F1, Accuracy}"
    source: "{URL to SOTA paper}"
    dataset: "{Link to benchmark dataset}"

nodes:
  - id: H-000  # The Root
    hypothesis: "{Core project hypothesis}"
    status: completed
    performance: {value}
    avenues: [H-001, H-002]
    
  - id: H-001
    parent: H-000
    hypothesis: "{Variant/Avenue hypothesis}"
    status: pending  # pending | in_progress | completed | discarded | blocked
    target_improvement: {value}
    actual_performance: null
    assigned_agent: null
    branch: null
    deliverables:
      blog: null
      arxiv: null
    notes: []
```

### Node Status Definitions

- **pending**: Ready to be picked up by a Worker agent.
- **in_progress**: Currently being researched/implemented by an agent.
- **completed**: Research finished and performance improved upon parent.
- **discarded**: Research finished but performance did not meet the target/parent.
- **blocked**: Dependencies (parents) are not yet completed.

## 2. Work-Item Metadata Schema (`metadata.yaml`)

Each research strand (branch) contains a `metadata.yaml` to track its local state and facilitate agent handoffs.

### Schema Definition

```yaml
# metadata.yaml

node_id: H-001
branch_name: research/H-001-gnn-drug-discovery
status: in_progress  # in_progress | awaiting_review | completed | discarded

current_owner:
  id: "Agent-007"
  session_id: "S-456"
  role: "worker"  # strategist | planner | worker | auditor

parent_performance: 0.92
target_improvement: 0.02
actual_performance: null

handoff:
  next_role: "auditor"  # The next agent type expected to act
  instructions: "SOTA baseline and initial implementation complete. Ready for verification."
  timestamp: "2026-02-28T09:10:00Z"

milestones:
  - id: baseline
    status: completed
    completed_at: "2026-02-28T08:30:00Z"
  - id: implementation
    status: in_progress
  - id: benchmarking
    status: pending
  - id: synthesis
    status: pending
```

## 3. Git Branching & Handoff Conventions

To maintain a consistent lineage across 20+ agents, the following conventions are enforced:

### Branching Strategy

- **Main Branch (`main`)**: Contains the `hypothesis-dag.yaml` and the verified, integrated research deliverables (blog posts, papers, and code).
- **Research Branches (`research/H-{ID}-{topic}`)**: Dedicated branches for individual nodes in the DAG. All implementation, benchmarking, and synthesis occur on these branches.

### Handoff Protocol

1. **Claiming a Strand**:
   - Agent checks `hypothesis-dag.yaml` for a `pending` node.
   - Creates/checks out the branch and updates `metadata.yaml` with its ID and `role`.
   - Commits and pushes to "soft-lock" the strand.

2. **Sequential Transitions**:
   - Only one role works on a branch at a time (e.g., Worker -> Auditor).
   - The current agent completes its milestones and updates the `handoff` section in `metadata.yaml`.
   - The next agent role picks up the strand by identifying the `next_role` in `metadata.yaml`.

3. **Conflict Resolution**:
   - If two agents attempt to claim the same strand simultaneously, the first push to the branch wins (Git native locking).
   - The second agent must re-read the DAG and pick a different `pending` node.

4. **Integration (The Merge)**:
   - Once a node is marked `completed` and passed by the Auditor/Human review, a PR is opened to merge the research branch into `main`.
   - Post-merge, the node status is updated in `hypothesis-dag.yaml` on the `main` branch.
