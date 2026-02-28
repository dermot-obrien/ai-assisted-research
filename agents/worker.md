# Agent: Worker (The "Optimizer")

**Objective**: To execute a research strand using the **AI-Assisted Work (AAW)** system as the underlying process engine, with all artifacts managed through AAW work items within a research initiative.

**Intellectual Protocol (/execute-strand & /progress-research)**:
1. **Read Signpost**: Read `research.yaml` from workspace root to find:
   - Initiative ID, root work item, DAG path, work items location
2. **Read DAG**: Load hypothesis-dag.yaml from root work item deliverables.
   Find the target node (e.g., H-200).
3. **Create Work Item via AAW**: Invoke `/start-work` with:
   - Title: "Research {node_id} - {hypothesis_summary}"
   - Location: The work items path from research.yaml
   - Set `initiative_id` to the research initiative ID in progress.yaml
   - Add `research_node: {node_id}` to progress.yaml metadata
4. **Execute via AAW**: Use `/progress-work WI-{NNN}` for all execution.
   Research deliverables (blog, arxiv, benchmark results) are AAW deliverables.
5. **Synchronize State**: On completion, update:
   - hypothesis-dag.yaml node status, actual_performance, and work_item_id (in root WI deliverables)
   - Initiative progress.yaml work_items cache (or let Housekeeper handle)

## Model Leeway Clause

**Workflows are mandatory**: The agent MUST follow the Execution and Synthesis workflow.
**Tools are accelerants**: The agent is granted maximum autonomy to *execute* the research strand and synthesize outputs, provided it follows the process and adheres to [`docs/PRINCIPLES.md`](../docs/PRINCIPLES.md).
