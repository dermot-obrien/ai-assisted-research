# Sync Research Result

The return path from AAW execution to research lineage. It ensures the master map reflects the
work actually performed.

Usage: `/research sync {node_id} {WI_id}`, for example
`/research sync H-001 WI-042`

## Phase 1: Verify the context

1. **Locate the work item.** `{work_items_path}/{WI_id}/` must exist and its `progress.yaml`
   status must be `done`. Syncing an unfinished work item records a result that does not exist
   yet.
2. **Locate the DAG**, `hypothesis-dag.yaml` or `hypothesis-tree.md`.
3. **Validate the node.** `{node_id}` must exist in the DAG and be `in_progress`.

## Phase 2: Extract the results

1. **Metrics**: `actual_performance` from the work item's `metadata.yaml`.
2. **The capsule.** With `vault` set in `research.yaml`, the node must name the capsule the metric
   came from in `capsules`, and its `result.value` must be the metric being recorded. Check it is
   intact: `vault.py verify <node>/<capsule id> --sha256 <hash>`. With no capsule, capture the run
   now if it can still be run (`vault.py run`), or with `vault.py capture` if only its outputs remain,
   noting that in `--note`; a result with neither stays `in_progress`.
3. **Findings**: the latest `finding` from the `activities` list in `progress.yaml`.
4. **Deliverables**: confirm the work item's products include the required research outputs,
   whether blog, arXiv draft or pivot report.

## Phase 3: Update the lineage

1. **Set the status** against the target that was fixed before the result was known:

   | Outcome | Status |
   |---------|--------|
   | Performance met or exceeded the target | `validated` |
   | Performance failed the target | `ineffective` |
   | Research stopped early | `discarded` |

   The capsule's evidence class (`vault.py show <capsule>`) limits the status, when the framing
   fixed windows (the same table as the experiment-vault protocol, 6.7.2):

   | Evidence class of the capsule | Met the target | Missed it |
   |---|---|---|
   | `exploratory` | none: the node stays `in_progress` | none |
   | `backtest` | `backtested`, or `validated` if the framing fixed no holdout or forward window | `ineffective` |
   | `holdout` | `holdout_passed`, or `validated` if the framing fixed no forward window | `ineffective` |
   | `forward`, at a checkpoint | `forward_testing`, and `validated` at the checkpoint the rule names | `contested`, or `retired` by the retire rule |
   | `untracked` | `validated`, for a node that fixed no window | `ineffective` |

   With a runtime that requires parity, no status moves until
   `vault.py parity <node>/<capsule>` exits 0: another machine or platform has replayed the
   capsule identically. Until then the node stays `in_progress`, and a parity replay that
   differs makes it `contested`.

   `ineffective` is a result, not a failure. Record it with the same care as a success; the
   next person needs to know this avenue was tried.

2. **Record the metrics** in the node's `actual_performance`.
3. **Link the deliverables** to the node.
4. **Append the evidence**: a note summarising the finding and linking the work item.

## Phase 4: Finalise

1. **Commit** the updated DAG and the synthesised articles.
2. **Refresh the node index.** A completed node may unblock its children, moving them from
   `blocked` to `ready`. Skipping this leaves work invisible.
3. **Update the dashboard**: run `/research housekeep`.
4. Optionally archive the work item to reduce clutter.

## Phase 5: Hand the conclusion back

Research decides whether to deliver; it does not deliver. Where the node began as an AAW
inquiry, re-triage its conclusion into AAW, per the AAW inquiry seam
([inquiry-seam.md](inquiry-seam.md)):

| Status | Hand back |
|--------|-----------|
| `validated` | Offer `/work start` for the delivery item that implements the proven approach: usually an intervention, or a change if it is local. Link the node. |
| `ineffective` | Close the inquiry as a lesson. The negative result recorded in the DAG is the deliverable; open no delivery item. |
| `discarded` | Close the inquiry, recording why the research stopped. |

If the finding settles an architectural choice, such as adopting one approach over another,
propose an AI-Assisted Architecture Decision Record (`DR-NNN`) that cites the node and the
work item. AAR records the finding, AAA the decision, and AAW delivers the change.

Propose these hand-offs; do not open the item or the record unasked. Whether a result is
worth delivering is the user's call.

## When metrics are missing

Try to synthesise them from `changes.md` and the session logs before failing the sync. If they
genuinely cannot be reconstructed, say so and leave the node `in_progress` rather than
recording a result you had to invent.

## Model leeway

The workflow is mandatory. The tools are a reference implementation: find better ways to
execute the steps if you can, provided you follow the process and adhere to the project's
research principles ([principles.md](principles.md), or the workspace's own copy where it governs one).

## Related skills

- `/research run` produces what this flow returns.
- `/research housekeep` regenerates the index and dashboard.
- `/research audit` verifies a result before or after it is synced.