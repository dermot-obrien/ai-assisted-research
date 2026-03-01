# Agent: Start Hypothesis

**Objective**: Scoping and planning of a research hypothesis by delegating to the AAW work management system.

This command is the **Research Design** phase. It maps directly to the AAW **`/start-work`** command. It takes a hypothesis node from the RMS master lineage and initializes a Work Item blueprint for exploration.

**Command**: `/start-hypothesis {node_id}`

---

## Protocol

### Phase 1: Research Context Extraction
1. **Load Node**: Locate the node in `hypothesis-dag.yaml` (or `hypothesis-tree.md`) matching `{node_id}`.
2. **Extract Metadata**: Gather the hypothesis text, SOTA targets, datasets, and parent evidence.

### Phase 2: Delegate to AAW `/start-work`
Invoke the standard AAW `/start-work` protocol with the following parameters:

*   **Work Item Title**: `{node_id}-research-{short-topic}`
*   **Source of Truth**: The hypothesis node text.
*   **Intent**: "Investigate {hypothesis}. Baseline SOTA, implement change, and quantify improvement."
*   **Acceptance Criteria**: Derived from the node's SOTA targets and metric requirements.
*   **Research Phase**: Leverage the hypothesis node's evidence and key competitors to populate the `research.md`.

### Phase 3: Update Research Lineage
Once the AAW Work Item is planned and committed:
1. **Link Work Item**: Record the generated `WI-{NNN}` ID in the DAG node's metadata.
2. **Change Status**: Update the node status in `hypothesis-dag.yaml` from `pending` to **`framed`**.

---

## Model Leeway Clause

**Delegate, Don't Re-implement**: The agent MUST follow the AAW `/start-work` protocol for all scoping, planning, and task decomposition. Do not attempt to create work item folders or documents manually if the AAW system is available.

**Framing is Archival**: The goal is to capture the "Experimental Design" while the idea is fresh. Even if implementation is delayed, the plan remains as a blueprint in the work item.
