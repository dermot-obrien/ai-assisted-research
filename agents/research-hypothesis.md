# Agent: Research Hypothesis

**Objective**: Begin research on a specific hypothesis node from the DAG, using the AAW work management system as the process engine.

This is the primary bridge between the Research Management System (RMS) and AI-Assisted Work (AAW). It takes a hypothesis node — which already contains the research question, evidence, SOTA targets, and datasets — and creates a properly scoped AAW work item to execute the research.

**Command**: `/research-hypothesis {node_id}`

**Example**: `/research-hypothesis 6.2`

---

## Prerequisites

Before invoking this command, the following must exist:

1. **Hypothesis DAG** — Either `hypothesis-tree.md` or `hypothesis-dag.yaml` in the repository root or its documentation folder.
2. **AAW framework** — The standard AI-Assisted Work management system must be active.
3. **Node must exist** — The referenced node ID must appear in the hypothesis tree/DAG.

---

## Protocol

### Phase 0: Load Hypothesis Context

1. **Locate the hypothesis tree/DAG.** Search for `hypothesis-dag.yaml` or `hypothesis-tree.md` in the root or `docs/`.
2. **Extract the target node.** Parse the hypothesis tree for the node matching `{node_id}`.
3. **Validate readiness.** The node should be in a state that warrants research (e.g., `pending` or `unexplored`).

### Phase 1: Derive Scope from Hypothesis

The hypothesis node **is** the scope source. Create a new AAW work item in the unified hierarchy:

1. **Determine work item location.** All research work resides in the standard `change/work-items/` directory.
2. **Identifier Convention**: Use the standard `WI-{NNN}` prefix and add a `-research-` suffix to the title (e.g., `WI-042-research-gnn-optimization`).
3. **Create `scope.md` and `scope-ai.md`** as described in the AAW `start-work` protocol, but derive all intent, criteria, and context directly from the hypothesis node.

### Phase 2: Discovery & Planning

Follow the standard AAW `start-work` Phase 2 and 3. Ensure the `progress.yaml` includes research-specific fields:
- **`finding`**: A concise summary of what was learned during the activity.
- **`prompted_by`**: The specific evidence or observation that led to this activity.

### Phase 3: Execution

Hand off to the standard AAW `/progress-work` protocol. All implementation, benchmarking, and article synthesis occur within the `change/work-items/WI-{NNN}/` folder.

### Phase 4: Synchronize Result (The Final Loop)

Once the AAW work item is marked `done`, the agent MUST invoke the **`/sync-research-result`** command to pull the findings, metrics, and deliverables back into the master RMS Lineage DAG.

---

## Model Leeway Clause

**Process Integrity is Mandatory**: Agents MUST use the `/research-hypothesis` and `/sync-research-result` commands to bridge the RMS lineage and AAW execution.

**Structural Adaptation**: Agents have full leeway to adapt the implementation of a research strand within the AAW work item. If the hypothesis requires a different set of activities or tools than originally planned, the agent SHOULD update the `plan.md` and `progress.yaml` to reflect the reality of the discovery, provided the *Lineage Continuity* (Principle 2) is preserved.

**Synthesis Innovation**: If an agent discovers a more effective way to present research results (e.g., a new visualization or a deeper technical analysis), it should adopt that method in the deliverables while still fulfilling the core requirements of the Blog and arXiv templates.

