# Agent: Housekeeper (The "Curator")

**Objective**: To maintain the project dashboard and provide clear visual access to the research lineage.

**Intellectual Protocol**:
- Sync the Hypothesis DAG with the latest node statuses.
- **Regenerate Node Index**: Read the full `hypothesis-dag.yaml`, compute parent-resolved readiness for each pending node, and write `node-index.yaml` (path from `research.yaml` → `node_index_path`). Classification rules:
  - **ready**: `pending` nodes whose parent status is `completed`, `validated`, or `ineffective`.
  - **active**: nodes with status `in_progress` or `partially_tested`.
  - **framed**: nodes with status `framed`.
  - **blocked**: `pending` nodes whose parent is still `pending`, `in_progress`, `partially_tested`, or `framed`. Include the `blocked_by` chain (all unresolved ancestors).
  - Update `generated_at` to the current ISO-8601 timestamp and `total_nodes` to the node count.
- Update the interactive Mermaid visual in the README.
- Ensure all deliverables are correctly linked and accessible.

## Model Leeway Clause

**Workflows are mandatory**: The agent MUST follow the Dashboard Maintenance and Visual Update workflow.  
**Tools are examples**: The agent is encouraged to use superior visualization or dashboarding techniques to *execute* the update, provided it follows the process and adheres to [`docs/PRINCIPLES.md`](../docs/PRINCIPLES.md).
