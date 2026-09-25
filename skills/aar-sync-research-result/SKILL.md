---
name: aar-sync-research-result
description: Return a completed work item's metrics, findings and deliverables to the hypothesis DAG, setting the node to validated, ineffective or discarded against its target, then regenerating the node index so unblocked children become ready. Use when asked to sync or synchronise a research result, close out a hypothesis, or record what an experiment found back into the lineage.
license: CC-BY-4.0
compatibility: Reads research.yaml at the workspace root. Delegates to AI-Assisted Work, so the /aaw-* skills must be installed.
metadata:
  author: dermot-obrien
  framework: aar
  version: "1.2.0"
---

# Sync Research Result

The return path from AAW execution to research lineage. It ensures the master map reflects the
work actually performed.

Usage: `/aar-sync-research-result {node_id} {WI_id}`, for example
`/aar-sync-research-result H-001 WI-042`

## Phase 1: Verify the context

1. **Locate the work item.** `{work_items_path}/{WI_id}/` must exist and its `progress.yaml`
   status must be `done`. Syncing an unfinished work item records a result that does not exist
   yet.
2. **Locate the DAG**, `hypothesis-dag.yaml` or `hypothesis-tree.md`.
3. **Validate the node.** `{node_id}` must exist in the DAG and be `in_progress`.

## Phase 2: Extract the results

1. **Metrics**: `actual_performance` from the work item's `metadata.yaml`.
2. **Findings**: the latest `finding` from the `activities` list in `progress.yaml`.
3. **Deliverables**: confirm the work item's products include the required research outputs,
   whether blog, arXiv draft or pivot report.

## Phase 3: Update the lineage

1. **Set the status** against the target that was fixed before the result was known:

   | Outcome | Status |
   |---------|--------|
   | Performance met or exceeded the target | `validated` |
   | Performance failed the target | `ineffective` |
   | Research stopped early | `discarded` |

   `ineffective` is a result, not a failure. Record it with the same care as a success; the
   next person needs to know this avenue was tried.

2. **Record the metrics** in the node's `actual_performance`.
3. **Link the deliverables** to the node.
4. **Append the evidence**: a note summarising the finding and linking the work item.

## Phase 4: Finalise

1. **Commit** the updated DAG and the synthesised articles.
2. **Refresh the node index.** A completed node may unblock its children, moving them from
   `blocked` to `ready`. Skipping this leaves work invisible.
3. **Update the dashboard**: run `/aar-housekeep`.
4. Optionally archive the work item to reduce clutter.

## When metrics are missing

Try to synthesise them from `changes.md` and the session logs before failing the sync. If they
genuinely cannot be reconstructed, say so and leave the node `in_progress` rather than
recording a result you had to invent.

## Model leeway

The workflow is mandatory. The tools are a reference implementation: find better ways to
execute the steps if you can, provided you follow the process and adhere to the project's
research principles (`docs/PRINCIPLES.md` in the AI-Assisted Research framework, or the
workspace's own copy where it governs one).

## Related skills

- `/aar-progress-hypothesis` produces what this skill returns.
- `/aar-housekeep` regenerates the index and dashboard.
- `/aar-run-audit` verifies a result before or after it is synced.