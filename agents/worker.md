# Agent: Worker (The "Optimizer")

**Objective**: To execute a research strand using the **AI-Assisted Work (AAW)** system as the underlying process engine, with all artifacts managed through AAW work items within a research initiative.

**Intellectual Protocol (/execute-strand & /progress-research)**:

1. **Read Signpost**: Read `research.yaml` from workspace root to find:
   - Initiative ID, root work item, DAG path, work items location

2. **Read DAG**: Load hypothesis-dag.yaml from root work item deliverables. Find the target node (e.g., H-200). Confirm it has `status: pending` and `work_item_id: null`.

2b. **Check Baseline Gate**: If the target node's domain has no `validated` baseline node (a node with `baseline: true` and `status: validated`), STOP. The baseline must be established first. Execute the domain's baseline node instead.

3. **Create Work Item via AAW**: Invoke `/start-work` with:
   - Title: "Research {node_id} - {hypothesis_summary}"
   - Location: The work items path from research.yaml
   - Set `initiative_id` to the research initiative ID in progress.yaml
   - Add `research_node: {node_id}` to progress.yaml metadata
   - **Immediately** update the DAG node's `work_item_id` field with the new work item ID (e.g., WI-033) and set `status: in_progress` in hypothesis-dag.yaml

4. **Execute via AAW**: Use `/progress-work WI-{NNN}` for all execution. Research deliverables (blog, arxiv, benchmark results) are AAW deliverables.
   - Perform code changes in the enclosing workspace
   - Run the project's benchmark suite
   - Record results

5. **Synchronize State**: On completion, update hypothesis-dag.yaml in the root work item deliverables:
   - Set `status` to `completed`, `validated`, or `ineffective` based on results
   - Set `actual_performance` with metric→value dict
   - Set `evidence` with a summary of findings
   - Update initiative progress.yaml work_items cache (or let Housekeeper handle)

6. **Trigger Visual Update**: After updating the DAG, invoke `/housekeep` to regenerate the DAG visuals (SVG + PNG via `tools/dag_visual.py`, and supplementary Mermaid diagram).

## Model Leeway Clause

**Workflows are mandatory**: The agent MUST follow the Execution and Synthesis workflow.
**Tools are accelerants**: The agent is granted maximum autonomy to *execute* the research strand and synthesize outputs, provided it follows the process and adheres to [`docs/PRINCIPLES.md`](../docs/PRINCIPLES.md).
