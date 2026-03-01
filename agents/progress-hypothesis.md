# Agent: Progress Hypothesis

**Objective**: Execute the implementation and benchmarking of a research hypothesis by delegating to the AAW work management system.

This command is the **Research Execution** phase. It maps directly to the AAW **`/progress-work`** command. It activates a "framed" hypothesis and manages the ongoing implementation loop.

**Command**: `/progress-hypothesis {WI_id} {node_id}`

---

## Protocol

### Phase 1: Activation (First-time execution only)
If implementation has not yet started for this hypothesis:
1. **Verify State**: Confirm the node in `hypothesis-dag.yaml` is `framed`.
2. **Setup Environment**: Create the Git research branch: `git checkout -b research/{node_id}-{topic}`.
3. **Initialize Metrics**: Ensure the research work item's `metadata.yaml` is configured to track the `parent_performance` and `target_metric`.
4. **Update DAG**: Change node status from `framed` to **`in_progress`**.

### Phase 2: Delegate to AAW `/progress-work`
Invoke the standard AAW `/progress-work {WI_id}` protocol to execute tasks.

*   **Finding-Driven Chain**: For every AAW activity completed, the agent MUST ensure a `finding` and `prompted_by` field is recorded in the work item's `progress.yaml`.
*   **Scientific Rigor**: Use the AAW execution loop to perform code changes, data processing, and benchmarking.

### Phase 3: Synthesis & Synchronization
Once the AAW Work Item reaches `done` status:
1. **Generate Outputs**: Synthesize the Blog, arXiv, or Pivot report using the `templates/` in the RMS repository.
2. **Synchronize**: Invoke **`/sync-research-result`** to bridge the metrics and findings back to the master Lineage DAG.

---

## Model Leeway Clause

**Delegate Execution**: The agent SHOULD use the AAW `/progress-work` protocol for task claiming, locking, and activity updates. 

**Research Specifics**: While AAW handles the "Work," the agent remains responsible for the "Research"—specifically ensuring that every technical result is translated into a scientific finding for the lineage.
