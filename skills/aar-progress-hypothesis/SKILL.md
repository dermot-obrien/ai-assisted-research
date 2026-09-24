---
name: aar-progress-hypothesis
description: Execute and benchmark a framed hypothesis: create the research branch, move the node to in_progress, delegate the task loop to AAW progress-work recording a finding per activity, then synthesise outputs and synchronise results back to the lineage. Use when asked to progress, execute, run or implement a hypothesis or research node that has already been framed.
license: CC-BY-4.0
compatibility: Reads research.yaml at the workspace root. Delegates to AI-Assisted Work, so the /aaw-* skills must be installed.
metadata:
  author: dermot-obrien
  framework: aar
  version: "1.2.0"
---

# Progress Hypothesis

The Research Execution phase. It maps onto AAW `/aaw-progress-work`: it activates a framed
hypothesis and runs the implementation loop.

Usage: `/aar-progress-hypothesis {WI_id} {node_id}`

## Phase 1: Activation, first execution only

1. **Verify state.** The node in `hypothesis-dag.yaml` must be `framed`. If it is still
   `pending`, run `/aar-start-hypothesis` first: executing an unframed hypothesis means
   designing the experiment while running it, which is how a result becomes unpublishable.
2. **Create the branch**: `git checkout -b research/{node_id}-{topic}`.
3. **Initialise metrics.** The work item's `metadata.yaml` tracks `parent_performance` and
   `target_metric`, so the comparison is fixed before the result is known.
4. **Update the DAG**: `framed` to `in_progress`.

## Phase 2: Delegate to AAW

Invoke `/aaw-progress-work {WI_id}` to execute the tasks.

Two research-specific obligations on top of the standard loop:

- **Finding-driven chain.** For every activity completed, record a `finding` and a
  `prompted_by` in the work item's `progress.yaml`. The chain of what prompted what is the
  part that cannot be reconstructed afterwards.
- **Scientific rigour.** Use the execution loop for the code changes, data processing and
  benchmarking, so the work is claimed, locked and recorded like any other.

## Phase 3: Synthesis and synchronisation

Once the work item reaches `done`:

1. **Generate the outputs** from the framework's `templates/`: the blog post, the arXiv draft,
   or the pivot report where the hypothesis did not hold. A negative result that is written up
   is a result; one that is not is a waste.
2. **Synchronise**: invoke `/aar-sync-research-result` to bridge the metrics and findings back
   to the lineage DAG.

## Division of responsibility

AAW handles the work: claiming, locking, activity state. You remain responsible for the
research, and specifically for translating every technical result into a scientific finding
the lineage can carry.

## Model leeway

The workflow is mandatory. The tools are a reference implementation: find better ways to
execute the steps if you can, provided you follow the process and adhere to the project's
research principles (`docs/PRINCIPLES.md` in the AI-Assisted Research framework, or the
workspace's own copy where it governs one).

## Related skills

- `/aar-start-hypothesis` designs what this skill executes.
- `/aar-sync-research-result` returns the result to the lineage.
- `/aar-run-audit` verifies the result independently.