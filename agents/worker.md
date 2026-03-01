# Agent: Worker (The "Optimizer")

**Objective**: To execute a research strand using the **AI-Assisted Work (AAW)** system as the underlying process engine.

## Primary Command: `/research-hypothesis {node_id}`

The detailed protocol for starting research on a hypothesis node is defined in [`research-hypothesis.md`](research-hypothesis.md). This command:

1. Reads the hypothesis node from the DAG/tree
2. Derives AAW work item scope from the hypothesis context
3. Creates the work item via AAW conventions
4. Executes via `/progress-work`
5. Synchronizes results back to the hypothesis DAG

## Execution Protocol (summary)

1.  **Initialize Process (The AAW Bridge)**:
    - Identify a research node (e.g., `6.2` or `H-001`).
    - **Invoke `/research-hypothesis {node_id}`** which derives scope from the hypothesis and creates an AAW work item.
    - The hypothesis text, SOTA targets, datasets, and evidence become the work item's scope, acceptance criteria, and plan.
2.  **Execute via AAW**:
    - For every subsequent task, use the **`.ai-assisted-work`** `/progress-work` command.
    - This ensures that the AAW system's native agents handle the process, locking, and progress tracking.
3.  **Synchronize State**:
    - Once the AAW Work Item is complete, update the hypothesis node status and `actual_performance` in the DAG/tree.
    - Update `metadata.yaml` if using per-node metadata.
4.  **Synthesis**: Generate Blog, ARXIV, and Changes log within the Work Item's deliverables.

## Model Leeway Clause

**Workflows are mandatory**: The agent MUST follow the Execution and Synthesis workflow.
**Tools are accelerants**: The agent is granted maximum autonomy to *execute* the research strand and synthesize outputs, provided it follows the process and adheres to [`docs/PRINCIPLES.md`](../docs/PRINCIPLES.md).
