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
    work_item_id: null          # Set when Worker creates AAW work item (e.g., WI-032)

  - id: H-001
    parent: H-000
    hypothesis: "{Variant/Avenue hypothesis}"
    status: pending  # pending | in_progress | completed | discarded | blocked
    target_improvement: {value}
    actual_performance: null
    assigned_agent: null
    branch: null
    work_item_id: null          # Set when Worker creates AAW work item (e.g., WI-033)
    deliverables:
      blog: null
      arxiv: null
    notes: []
```

**Note:** The `work_item_id` field links each DAG node to its corresponding AAW Work Item. When a Worker agent claims a node and creates a work item via `/start-work`, it records the work item ID here. This enables bidirectional navigation: from the DAG to the work item (via `work_item_id`) and from the work item to the DAG node (via `research_node` metadata in the work item's progress.yaml).

### Node Status Definitions

- **pending**: Ready to be picked up by a Worker agent.
- **in_progress**: Currently being researched/implemented by an agent.
- **completed**: Research finished and performance improved upon parent.
- **discarded**: Research finished but performance did not meet the target/parent.
- **blocked**: Dependencies (parents) are not yet completed.

## 2. Per-Node State Tracking (via AAW Work Items)

Each research strand's state is tracked by its AAW Work Item's `progress.yaml`, replacing the standalone `metadata.yaml` concept. The Work Item's progress.yaml includes a `research_node` metadata field linking it back to the DAG node.

### AAW Work Item Progress Metadata

When creating a work item for a research node, the Worker agent adds these fields to the work item's `progress.yaml`:

```yaml
# In the work item's progress.yaml
initiative_id: IN-001           # Links to the research initiative
# ... standard AAW fields ...

# Research-specific metadata (in progress.yaml metadata section or as top-level fields)
# research_node: H-001          # Back-pointer to the DAG node
```

### Migration from metadata.yaml

The previous `metadata.yaml` per-node concept is superseded by AAW's `progress.yaml`:

| Old (metadata.yaml) | New (AAW progress.yaml) |
|---------------------|------------------------|
| `node_id` | `research_node` metadata field |
| `branch_name` | `artifacts.branch` |
| `status` | Standard AAW `status` field |
| `current_owner` | AAW activity locks |
| `parent_performance` / `target_improvement` | In DAG node definition |
| `actual_performance` | Updated in DAG node on completion |
| `handoff` | AAW activity dependency model |
| `milestones` | AAW activities and tasks |

## 3. Git Branching & Handoff Conventions

To maintain a consistent lineage across 20+ agents, the following conventions are enforced:

### Branching Strategy

- **Main Branch (`main`/`master`)**: Contains the `hypothesis-dag.yaml` (via root work item deliverables) and the verified, integrated research deliverables.
- **Work Item Branches (`wi/WI-{NNN}-{topic}`)**: Uses AAW's standard branch naming convention. Each research node gets its own work item and branch. All implementation, benchmarking, and synthesis occur on these branches.

### Handoff Protocol

1. **Claiming a Strand**:
   - Agent reads `research.yaml` signpost to locate the DAG.
   - Checks `hypothesis-dag.yaml` for a `pending` node.
   - Creates an AAW Work Item via `/start-work` with `initiative_id` set to the research initiative.
   - AAW's activity locking prevents concurrent work on the same node.

2. **Sequential Transitions**:
   - AAW's activity dependency model handles sequential work (e.g., implementation → benchmarking → synthesis).
   - Each activity within the work item represents a research milestone.
   - Agent handoffs use AAW's lock-and-release model instead of metadata.yaml handoff fields.

3. **Conflict Resolution**:
   - AAW's activity locking prevents two agents from working the same activity simultaneously.
   - DAG node's `work_item_id` field prevents duplicate work item creation for the same node.

4. **Integration (The Merge)**:
   - Once a node's work item is marked `done` and passed by the Auditor/Human review, a PR is opened.
   - Post-merge, the node status and `actual_performance` are updated in `hypothesis-dag.yaml` (in the root work item's deliverables).
