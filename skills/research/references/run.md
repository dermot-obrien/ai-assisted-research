# Progress Hypothesis

The Research Execution phase. It maps onto AAW `/work progress`: it activates a framed
hypothesis and runs the implementation loop.

Usage: `/research run {WI_id} {node_id}`

## Phase 1: Activation, first execution only

1. **Verify state.** The node in `hypothesis-dag.yaml` must be `framed`. If it is still
   `pending`, run `/research frame` first: executing an unframed hypothesis means
   designing the experiment while running it, which is how a result becomes unpublishable.
2. **Create the branch**: `git checkout -b research/{node_id}-{topic}`.
3. **Initialise metrics.** The work item's `metadata.yaml` tracks `parent_performance` and
   `target_metric`, so the comparison is fixed before the result is known.
4. **Update the DAG**: `framed` to `in_progress`.

## Phase 2: Delegate to AAW

Invoke `/work progress {WI_id}` to execute the tasks.

Two research-specific obligations on top of the standard loop:

- **Finding-driven chain.** For every activity completed, record a `finding` and a
  `prompted_by` in the work item's `progress.yaml`. The chain of what prompted what is the
  part that cannot be reconstructed afterwards.
- **Scientific rigour.** Use the execution loop for the code changes, data processing and
  benchmarking, so the work is claimed, locked and recorded like any other.
- **Every measured run goes through the vault.** With `vault` set in `research.yaml`, run each
  experiment whose numbers you will report through the experiment-vault skill, following its
  [protocol](../../experiment-vault/references/protocol.md): commit, run the command with `--dry-run`
  until it prints `ready`, then `vault.py run --node {node_id} --data ... --outputs ... --metrics ... --metric ... --seed ... -- <command>`,
  and verify and report the capsule as the protocol says. It keeps the code at its commit,
  the data, the environment, the command and the outputs as a capsule, and appends the capsule to
  the node. A number that did not come from a capsule cannot be replayed, so it is not the
  result; exploratory runs need not be captured. Without a vault configured, say so to the user
  once, and record the commit, data, seeds and command in the work item.

## Phase 3: Synthesis and synchronisation

Once the work item reaches `done`:

1. **Generate the outputs** from the skill's [`assets/templates/`](../assets/templates/): the blog post, the arXiv draft,
   or the pivot report where the hypothesis did not hold. A negative result that is written up
   is a result; one that is not is a waste.
2. **Synchronise**: invoke `/research sync` to bridge the metrics and findings back
   to the lineage DAG.

## Division of responsibility

AAW handles the work: claiming, locking, activity state. You remain responsible for the
research, and specifically for translating every technical result into a scientific finding
the lineage can carry.

## Model leeway

The workflow is mandatory. The tools are a reference implementation: find better ways to
execute the steps if you can, provided you follow the process and adhere to the project's
research principles ([principles.md](principles.md), or the workspace's own copy where it governs one).

## Related skills

- `/research frame` designs what this flow executes.
- `/research sync` returns the result to the lineage.
- `/research audit` verifies the result independently.