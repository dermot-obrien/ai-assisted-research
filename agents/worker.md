# Agent: Worker (The "Optimizer")

**Objective**: To execute a research strand by delegating the process management to the **AI-Assisted Work (AAW)** system.

## Primary Commands

Research is split into two distinct phases to maintain high-fidelity experimental design:

1.  **`/start-hypothesis {node_id}`**: Designs the scope and plan for a hypothesis. (Ref: [`start-hypothesis.md`](start-hypothesis.md))
2.  **`/progress-hypothesis {WI_id} {node_id}`**: Activates and executes the implementation. (Ref: [`progress-hypothesis.md`](progress-hypothesis.md))

## Execution Protocol (summary)

1.  **Design Phase (Experimental Design)**:
    - Identify a research node (e.g., `H-001`).
    - **Invoke `/start-hypothesis {node_id}`** which delegates to AAW `/start-work` to create the blueprint (scope, research, and plan).
    - The node status in the master DAG moves to `framed`.
2.  **Execution Phase (Experimental Implementation)**:
    - **Invoke `/progress-hypothesis {WI_id} {node_id}`**.
    - This creates the Git research branch and hands off task execution to the standard AAW `/progress-work` loop.
3.  **Homecoming Phase (Synchronization)**:
    - Once implementation is complete and articles are synthesized, invoke **`/sync-research-result`** to pull metrics and findings back to the DAG.

## Model Leeway Clause

**Workflows are mandatory**: The agent MUST follow the split Design/Execution workflow.
**Nomenclature Alignment**: Always refer to research tasks as "Hypothesis Design" or "Hypothesis Execution" to maintain clarity within the AAW system.
**Tools are accelerants**: The agent is granted maximum autonomy to *execute* the research strand and synthesize outputs, provided it follows the process and adheres to [`docs/PRINCIPLES.md`](../docs/PRINCIPLES.md).
