# Agent: Sync Research Result

**Objective**: Synchronize the findings, metrics, and deliverables from an AAW work item back to the Research Management System (RMS) Hypothesis DAG.

This command is the "Return Path" from AAW execution to RMS lineage tracking. It ensures the master map (the DAG) reflects the actual work performed in the trenches.

**Command**: `/sync-research-result {node_id} {WI_id}`

**Example**: `/sync-research-result H-001 WI-042`

---

## Protocol

### Phase 1: Context Verification
1. **Locate the AAW Work Item**: Verify that the directory `change/work-items/{WI_id}/` exists and its status in `progress.yaml` is `done`.
2. **Locate the Hypothesis DAG**: Identify the central `hypothesis-dag.yaml` (or `hypothesis-tree.md`).
3. **Validate the Node**: Ensure the `{node_id}` exists in the DAG and is currently `in_progress`.

### Phase 2: Extract Results from AAW
1. **Extract Metrics**: Read the `actual_performance` from `change/work-items/{WI_id}/metadata.yaml`.
2. **Extract Findings**: Read the latest `finding` from the `activities` list in `change/work-items/{WI_id}/progress.yaml`.
3. **Verify Deliverables**: Ensure the `deliverables/` folder contains the required research outputs (Blog, arXiv, or Pivot report).

### Phase 3: Update RMS Lineage
1. **Update DAG Status**:
   - If performance met/exceeded target: Set status to `validated`.
   - If performance failed target: Set status to `ineffective`.
   - If research was stopped early: Set status to `discarded`.
2. **Record Metrics**: Update the `actual_performance` field in the DAG for the node.
3. **Link Deliverables**: Update the `deliverables` section in the DAG node with the paths to the synthesized articles.
4. **Append Evidence**: Add a note to the node summarizing the finding and linking to the specific WI.

### Phase 4: Finalize & Housekeep
1. **Commit Changes**: Commit the updated DAG and any synthesized articles to the `main` branch.
2. **Update Visualization**: Run `/housekeep` to refresh the Mermaid/SVG dashboards.
3. **Archive Work Item**: (Optional) Mark the AAW work item as archived to reduce clutter in `change/work-items/`.

---

## Model Leeway Clause

**Synchronization is Mandatory**: The lineage graph MUST be updated when a research strand is completed.

**Synthesis Adaptation**: If the standard templates (Blog/arXiv) were modified during the AAW phase to better suit the findings, the agent should preserve those improvements when linking the deliverables back to the DAG.

**Error Handling**: If metrics or findings are missing from the AAW work item, the agent SHOULD attempt to synthesize them from the `changes.md` and session logs before failing the sync.
