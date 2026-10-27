# Start Hypothesis

The Research Design phase. It maps onto AAW `/work start`: it takes a hypothesis node from
the research lineage and initialises a work item blueprint for exploring it.

Usage: `/research frame {node_id}`

## Phase 1: Extract the research context

1. **Verify readiness, index first.** Read the node index per
   [references/node-selection.md](node-selection.md).
   - `{node_id}` in `ready`: proceed, its parents are resolved.
   - `{node_id}` in `blocked`: warn the user about the unresolved parents listed in
     `blocked_by` and confirm before proceeding.
   - Not found: the index is stale. Fall back to the full DAG.
2. **Load the node** from `hypothesis-dag.yaml`, or `hypothesis-tree.md` where that is still
   the source.
3. **Extract the metadata**: hypothesis text, SOTA targets, datasets, parent evidence.

## Phase 2: Delegate to AAW

Invoke `/work start` with:

| Parameter | Value |
|-----------|-------|
| Class | `intervention`, or `change` if the experiment touches one unit only |
| Work item title | `{node_id}-research-{short-topic}` |
| Source of truth | The hypothesis node text, verbatim |
| Intent | "Investigate {hypothesis}. Baseline SOTA, implement change, and quantify improvement." |
| Acceptance criteria | Derived from the node's SOTA targets and metric requirements |
| Research phase | Populate `research.md` from the node's evidence and key competitors |

State the class, and that the request comes from AAR. AAW triage would otherwise read an
uncertain hypothesis as an `inquiry` and route it straight back here. The inquiry is the
hypothesis; the experiment that tests it is known work.

Do not create work item folders or documents by hand. AAW owns that mechanism, and a
hand-rolled work item will not be found by the tools that expect one.

## Phase 2b: Fix what will be captured

Write into the work item's plan, before anything runs: the command that produces the result, the
inputs (`--data`) and outputs (`--outputs`, `--metrics`) by path inside the repository, the
seeds, the metric key, and the tolerance a replay must meet (`--rtol`, `--atol`). These are the
arguments of `vault.py run` in the experiment-vault skill. Fixing them now, like the target, is
what lets a later agent replay the experiment and know whether it held.

When the node is tested on data that grows or that the design could be fitted to, such as a
trading strategy's backtest, fix its evidence too ([datasets](../../experiment-vault/references/datasets.md)):

- **The datasets and windows**: the registered dataset and version, the backtest window it is
  developed on, the sealed holdout window it is judged on once, and the forward window it is
  tested on as data arrive. Define the backtest and forward windows that do not exist yet; a
  holdout window only for a span the person approved in the plan. The steps, and who does each, are
  the experiment-vault [protocol](../../experiment-vault/references/protocol.md), section 6.
- **The decision rule**: the target on the backtest, the target on the holdout, the forward
  checkpoints (after how much new data, against what threshold), and the rule that retires it.
  Which statuses the node can reach follows from the windows (the research-dag skill's
  `references/node-schema.md`): with a holdout or forward window fixed, a backtest alone never
  validates it.

## Phase 3: Update the lineage

1. Record the generated `WI-{NNN}` in the DAG node's metadata.
2. Move the node status from `pending` to `framed`.

## Framing is archival

The point is to capture the experimental design while the idea is fresh. Even if
implementation never starts, the plan survives as a blueprint, and a blueprint someone can
read later is worth more than an intention nobody wrote down.

## Model leeway

The workflow is mandatory. The tools are a reference implementation: find better ways to
execute the steps if you can, provided you follow the process and adhere to the project's
research principles ([principles.md](principles.md), or the workspace's own copy where it governs one).

## Related skills

- `/research run` executes what this flow designs.
- `/research lineage` adds the node if it does not exist yet.