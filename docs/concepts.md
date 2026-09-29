<!--
SPDX-FileCopyrightText: 2026 Dermot O'Brien
SPDX-License-Identifier: CC-BY-4.0
-->

# Concepts

The ideas you need to use AI-Assisted Research (AAR), in the order you meet them. The
[quick start](quick-start.md) shows most of them working; the [skills guide](skills.md)
says which skill does what.

## The workspace and research.yaml

AAR works inside a git repository, the workspace. Its root holds `research.yaml`, which
tells every tool where the research lives: the DAG, the node index, the work items and the
dashboard. The installer seeds it from
[`research.yaml.example`](../skills/research-dag/assets/research.yaml.example) and never
overwrites it. Paths in it are relative to the folder that holds it. Tools find it by
searching upward from the working directory, so you can run them from any subfolder.
[Configuration](configuration.md) lists every key.

## The hypothesis DAG

The research record is a directed acyclic graph of hypotheses, kept as YAML at `dag_path`
(conventionally `research/hypothesis-dag.yaml`). Each node is one hypothesis: a specific,
measurable change, a metric, a target, and the evidence it rests on. A node's `parent` is
the node that must be resolved before it can be tested, not merely the one that came before
it. The root is usually H-000, the state of the art or the current baseline, and every
avenue explored hangs beneath it.

The DAG is the lineage of ideas: read top to bottom, it shows how the thinking evolved and
what each step was measured against. A negative result stays in it, because the next
person needs to know that avenue was tried.

## Node ids

A flat DAG numbers nodes H-000, H-001, H-002. A DAG with hierarchical ids numbers a child
under its parent: H-204.4.26 after H-204.4.25, H-705 as the next in the H-700 block, H-204.1
to start a new level. `dag_update.py` allocates ids in whichever scheme the DAG already
uses. A letter suffix (H-204.4.25b) marks a node renamed because a concurrent writer took
its id first; see [the shared DAG store](#the-shared-dag-store).

## Node status

`status` says whether a hypothesis is true, as far as the research knows.

| Status | Meaning |
|---|---|
| `pending` | Proposed, not yet designed |
| `framed` | Experiment designed and a work item created; not yet running |
| `in_progress` | Running, on its own research branch |
| `partially_tested` | Some evidence, not yet conclusive |
| `contested` | A finding is challenged and unresolved |
| `validated` | Met or beat its target |
| `ineffective` | Tested and missed its target. A result, not a failure |
| `discarded` | Stopped before a result, with the reason recorded |
| `completed` | Resolved and closed; used for roots and legacy nodes |

The usual path is `pending` to `framed` to `in_progress` to `validated` or `ineffective`.
`dag_update.py --action update` sets any of these except `partially_tested` and
`completed`, which older DAGs carry and the tools still read.

## The node index and readiness

`generate_node_index.py` computes, for every open node, whether it can be worked now, and
writes the result to `node_index_path`:

| List | Holds |
|---|---|
| `ready` | `pending` nodes whose parent is `completed`, `validated` or `ineffective`, and pending roots |
| `active` | nodes at `in_progress`, `partially_tested` or `contested` |
| `framed` | nodes at `framed` |
| `blocked` | `pending` nodes whose parent is unresolved, with `blocked_by` naming every unresolved ancestor |

The research skills pick work from `ready` instead of scanning the DAG. An index older than
seven days, or missing a node, is treated as stale and the skills fall back to the DAG. So
regenerate the index after every change; `/aar-housekeep` and `/aar-sync-research-result`
do it for you.

## Roles and skills

Each workflow is an [Agent Skill](https://agentskills.io): a folder with a `SKILL.md` that
any skills-compatible agent reads. Each plays a role:

| Role | Skills |
|---|---|
| Discovery, the detective | `aar-init-research` reconstructs lineage in a repository whose research predates AAR |
| Specialist, the strategist | `aar-start-research` baselines the state of the art and designs the DAG; `aar-update-lineage` extends it |
| Worker, the optimiser | `aar-progress-research`, `aar-start-hypothesis`, `aar-progress-hypothesis`, `aar-sync-research-result` run a strand |
| Auditor, the validator | `aar-run-audit` checks a result is sound |
| Reconciler, the drift detector | `aar-reconcile` checks a result is live |
| Housekeeper, the curator | `aar-housekeep` keeps the index and dashboard true |

Two skills have no role of their own. `research-dag` is the engine: the Python tools every
research skill uses to change and read the DAG. `literature-discovery` searches the
literature and works on its own, without the rest of AAR. [AGENTS.md](AGENTS.md) describes
the roles in more depth.

## The three phases of a hypothesis, and AAW

Research splits into phases so the experimental design is fixed before the result is known.

1. Design. `/aar-start-hypothesis {node}` checks the node is ready, extracts its target and
   evidence, and asks AI-Assisted Work (`/aaw-start-work`) to create a work item for the
   experiment. The node moves to `framed`.
2. Execution. `/aar-progress-hypothesis {WI} {node}` opens the research branch
   `research/{node}-{topic}`, fixes the parent's performance and the target in the work
   item's `metadata.yaml`, moves the node to `in_progress`, and hands the task loop to
   `/aaw-progress-work`, recording a finding per activity.
3. Homecoming. `/aar-sync-research-result {node} {WI}` reads the measured result, sets the
   node to `validated`, `ineffective` or `discarded` against the target fixed in step 2,
   links the deliverables and regenerates the index.

AAW owns the work: work items, activities, claiming and locking. AAR owns the research:
the hypothesis, the metric and the finding. That is why the `aar-*` skills that create or
run work need the AAW skills installed. `/aar-progress-research` drives the three phases
without you naming a node.

## Deliverables

A finished hypothesis leaves a write-up in the work item's `deliverables/`, from the
templates in [`aar-progress-hypothesis/assets/templates/`](../skills/aar-progress-hypothesis/assets/templates/):
a blog post and an arXiv-style draft for a result that held, or a pivot report for one that
did not. `changes_template.md` records the research changes log.

## Audit: is it sound?

`/aar-run-audit` re-runs the benchmark in a clean room: the evaluation scripts under
`performance/benchmarks/` come from `main`, never from the branch under audit, because a
worker optimising against a benchmark can change the benchmark instead of the system.
[`audit_verify.py`](../skills/aar-run-audit/scripts/audit_verify.py) checks the recorded
performance against the parent's, that the deliverables exist, and with `--clean-room`
that the benchmarks match `main`.

## Adoption: is it live?

A validated node can be entirely absent from the running system. So each node carries a
second, independent state, `adoption.state`: `not_assessed`, `not_applicable`,
`not_adopted`, `partial`, `adopted` or `contradicted`. A node claiming `adopted`,
`partial` or `contradicted` owes a verification predicate: a shell command that exits 0
while the claim holds. `/aar-reconcile` runs every predicate and reports drift without
proposing fixes. [Adoption and drift](adoption-and-drift.md) is the full design.

## Housekeeping and the dashboard

`/aar-housekeep` regenerates the node index, checks that every hypothesis id mentioned in
code and docs exists in the DAG, and rebuilds `research/dashboard.html`: an interactive
graph of the DAG coloured by status, with experiments, breakthroughs, papers and
cross-node findings when those files exist.

## The shared DAG store

One YAML file has one writer at a time. When several machines or agents change one DAG,
set `dag_store` and `dag_project` in `research.yaml`. The DAG then lives in a separate git
repository as append-only JSON event files, one folder per project, so writers never merge
conflict. `dag_update.py` pulls, writes events, pushes with a retry, and regenerates the YAML
at `dag_path` as a view that every other tool reads unchanged. Concurrent edits to one field:
the later wins and the replaced value is reported. Concurrent adds under one id: the later
takes a letter suffix, recorded as an alias.
[The shared DAG store](../skills/research-dag/references/dag-store.md) has the event format
and the day-to-day commands.

## Where AAR meets AAW, and AAA

An AAW `inquiry`, work where nobody yet knows what to do, is an AAR hypothesis. AAR frames
and tests it, and hands the conclusion back to AAW as delivery work or closes it as a
lesson. A finding that settles an architectural choice can become a decision record in
AI-Assisted Architecture. [The AAW inquiry seam](aaw-inquiry-seam.md) is the contract.

## Principles and model leeway

Every skill ends with the same clause: the workflow is mandatory, the tools are a reference
implementation. An agent may find a better way to do a step, provided it follows the
process and the [research principles](PRINCIPLES.md): metric supremacy, lineage
continuity, one fundamental change per node, and the rest.
