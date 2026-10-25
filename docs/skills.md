<!--
SPDX-FileCopyrightText: 2026 Dermot O'Brien
SPDX-License-Identifier: CC-BY-4.0
-->

# Skills

The four skills and the research flows, what each does, when to use it, what it needs and what it leaves
behind. Each skill's `SKILL.md` is the definition the agent follows; this page is the
guide for people. Every skill ships the post-install check `bin/check.py`; see
[commands](commands.md#checkpy-every-skill).

Four skills. `research` is the method, one flow per row below. Until version 3.0.0 those flows were eleven skills, named in each section; the skill still answers to the old names. It stands on two skills that also work without it: `research-dag` owns the DAG and the only tools that change it, and `experiment-vault` keeps every measured run as a capsule that a later agent can replay. `literature-discovery` searches the literature and works on its own.

| Flow | Use it to | Needs |
|---|---|---|
| [`/research start`](#research-start) | Start a new research project | literature-discovery, AAW |
| [`/research init`](#research-init) | Reconstruct the lineage of existing research | AAW |
| [`/research lineage`](#research-lineage) | Add or revise hypotheses | nothing else |
| [`/research progress`](#research-progress) | Pick up the next ready node and drive it | AAW |
| [`/research frame`](#research-frame) | Design the experiment for one node | AAW |
| [`/research run`](#research-run) | Run a framed experiment | AAW |
| [`/research sync`](#research-sync) | Record a finished experiment in the DAG | AAW |
| [`/research audit`](#research-audit) | Check a result is sound | nothing else |
| [`/research retest`](#research-retest) | Check a recorded result still holds after a library, data or code change | experiment-vault |
| [`/research reconcile`](#research-reconcile) | Check results are live in the running system | nothing else |
| [`/research housekeep`](#research-housekeep) | Refresh the index, references and dashboard | nothing else |
| `/research dag` | The DAG tools every flow calls: the [research-dag](#research-dag) skill | research-dag |

Every flow changes the DAG through research-dag, which `research` requires. With `vault` set in
`research.yaml`, `/research frame`, `run`, `sync`, `audit` and `housekeep` also use the
experiment vault: frame fixes what a run will capture, run captures it, sync checks the result
has its capsule, audit replays it, and housekeep checks every result has one.

| Skill | Use it to | Needs |
|---|---|---|
| [research-dag](#research-dag) | Change and read the hypothesis DAG, alone or in a shared DAG store | Python, PyYAML, git for a store |
| [experiment-vault](#experiment-vault) | Keep each experiment as a replayable capsule, and replay it | Python, PyYAML, git; the gcloud CLI for a `gs://` vault |
| [literature-discovery](#literature-discovery) | Search the literature, on its own or for a baseline | Python, requests, PyYAML, network |

"AAW" means AI-Assisted Work's `work` skill (`/work start`, `/work progress`,
`/work initiative`), 3.0.0 or later, installed in the same workspace. It replaced the five
`aaw-*` work skills in AI-Assisted Work 4.0.0. The exact version ranges are in
[`bundle.json`](../bundle.json).

A typical project runs them in this order: `/research start` (or `/research init`),
then for each node `/research frame`, `/research run`,
`/research sync`, with `/research audit` before or after the sync,
`/research lineage` whenever a new avenue appears, `/research retest` when something a
result rests on changes, and `/research housekeep` and `/research reconcile` from time to
time.

## research start

`/research start`. Was `aar-start-research`.

Role: Specialist. Starts a research project from nothing.

- Invoke: `/research start {topic}`, or "start a research project on ...".
- Does: baselines the state of the art with `literature-discovery`, recording the best
  published result with its citation; turns the gap into measurable variants; proposes the
  DAG, each node with hypothesis, target, datasets and parent evidence; asks AAW for the
  initiative (`/work initiative`) and the root work item (`/work start`).
- Leaves: `research.yaml` (copied from the skill's example when the workspace had none), `research/hypothesis-dag.yaml`, an AAW initiative and root work item, and a signpost to where the research lives.
- Use `/research init` instead when the research already happened.
- Definition: [references/start.md](../skills/research/references/start.md).

## research init

`/research init`. Was `aar-init-research`.

Role: Discovery. Brings AAR to a repository whose research predates it.

- Invoke: `/research init`, or "reconstruct the research lineage of this repository".
- Does: finds the kernel idea in early commits and docs, identifies major shifts as
  branches, cites a commit, pull request or file and line for every claim, confirms the
  lineage with you, then writes the DAG (creating `research.yaml` from the skill's example when there is none) and sets up the AAW initiative and root work item.
  Where evidence is thin it marks nodes as inferred rather than guessing.
- Tool: `scripts/discovery.py [--confirm]` gathers first markers; see
  [commands](commands.md#research-scriptsdiscoverypy).
- Definition: [references/init.md](../skills/research/references/init.md).

## research lineage

`/research lineage`. Was `aar-update-lineage`.

Role: Specialist. Extends the search space.

- Invoke: `/research lineage`, or "add a hypothesis that ...".
- Does: re-baselines if the state of the art has moved, formulates a specific, measurable
  variant, places it under the parents it truly depends on, records the evidence, and
  regenerates the node index. It pushes back on a node that cannot be measured.
- Tools: research-dag's `dag_update.py` and `generate_node_index.py`.
- Definition: [references/lineage.md](../skills/research/references/lineage.md).

## research progress

`/research progress`. Was `aar-progress-research`.

Role: Worker. Drives a strand without you naming a node.

- Invoke: `/research progress`, or "continue the research".
- Does: picks the next node from the index's `ready` list (warning before working a
  `blocked` one), then runs the three phases through `/research frame`,
  `/research run` and `/research sync`.
- Reference: [node-selection.md](../skills/research/references/node-selection.md).
- Definition: [references/progress.md](../skills/research/references/progress.md).

## research frame

`/research frame`. Was `aar-start-hypothesis`.

The design phase for one node.

- Invoke: `/research frame {node_id}`.
- Does: checks the node is `ready` (or warns if `blocked`), extracts its hypothesis,
  targets, datasets and parent evidence, and asks `/work start` for a work item titled
  `{node_id}-research-{topic}`, classed as an intervention (or a change if local) so AAW
  does not route it back as an inquiry. With a vault configured, writes into the plan what
  the run will capture: the command, the inputs and outputs by path, the seeds, the metric
  key and the tolerance a replay must meet. Records the work item on the node and moves it
  to `framed`.
- Leaves: a work item with `scope.md`, `research.md` and `plan.md`, even if the experiment
  never runs.
- Definition: [references/frame.md](../skills/research/references/frame.md).

## research run

`/research run`. Was `aar-progress-hypothesis`.

The execution phase for one framed node.

- Invoke: `/research run {WI_id} {node_id}`.
- Does: on first run, checks the node is `framed`, creates `research/{node_id}-{topic}`,
  fixes `parent_performance` and `target_metric` in the work item's `metadata.yaml`, and
  moves the node to `in_progress`. Then hands the task loop to `/work progress`,
  recording a `finding` and `prompted_by` per activity. With a vault configured, every run
  whose numbers will be reported goes through `vault.py run`, after a commit, so it is kept
  as a capsule on the node; without one, it says so once and records the commit, data, seeds
  and command in the work item. When the work item is done, writes
  the blog post and arXiv draft, or a pivot report, from
  [`assets/templates/`](../skills/research/assets/templates/), and calls
  `/research sync`.
- Definition: [references/run.md](../skills/research/references/run.md).

## research sync

`/research sync`. Was `aar-sync-research-result`.

The return path from a finished work item to the DAG.

- Invoke: `/research sync {node_id} {WI_id}`.
- Does: checks the work item is `done` and the node `in_progress`; reads
  `actual_performance` from `metadata.yaml` and the latest finding from `progress.yaml`;
  with a vault configured, checks the node names the capsule the metric came from and that
  it is intact (`vault.py verify --sha256`), capturing the run first if it has none;
  sets the node to `validated` (met the target), `ineffective` (missed it) or `discarded`
  (stopped early); links the deliverables; commits; regenerates the index and dashboard.
  Where the node began as an AAW inquiry it proposes the hand-back: a delivery work item for
  a validated result, a closed lesson otherwise, and a decision record where the finding
  settles an architectural choice. It proposes; it does not open them unasked.
- If metrics are missing it tries to reconstruct them and otherwise leaves the node
  `in_progress` rather than invent a result. With a vault configured, a result with no
  capsule, which can neither be run again nor captured from its outputs, also stays
  `in_progress`.
- Definition: [references/sync.md](../skills/research/references/sync.md).

## research audit

`/research audit`. Was `aar-run-audit`.

Role: Auditor. Is the result sound?

- Invoke: `/research audit`, or "audit the result for H-001".
- Does: first replays the node's capsule, where it has one (`vault.py replay`), which shows
  the result can be made again from what was recorded; then re-runs the benchmarks in a
  clean room, with evaluation scripts from `main`, never
  from the branch under audit; checks the code changes are clean; checks the data, the
  measured performance and the written claims agree. Reports what reproduced as well as
  what did not, and never changes the node's status itself.
- Tool: `scripts/audit_verify.py`; see [commands](commands.md#research-scriptsaudit_verifypy).
- Definition: [references/audit.md](../skills/research/references/audit.md).

## research retest

`/research retest`. New in 4.0.0.

Does a recorded result still hold now that something changed?

- Invoke: `/research retest {node_id} [what changed]`, for example
  `/research retest H-001 "numpy 2.1"`, or `/research retest --all-validated "new prices.csv"`
  for every validated node the change touches (it confirms before running more than three).
- Does: takes the node's newest capsule of kind `run` and verifies it, then replays it with
  the change: `vault.py replay` for nothing changed, `--pip <package>==<version>` for a
  library, `--setup none` for the environment as a whole, or a new `vault.py run
  --retest-of <capsule>` after committing changed code or data. Each records a `retest`
  capsule on the node with its verdict.
- Leaves: a note on the node for every verdict. A `drifted` retest of a `validated` or
  `ineffective` node also moves it to `contested`, with the retest capsule in
  `capsules` as the evidence, and proposes a child hypothesis or an audit; it never sets the node back
  to `validated` itself. A `failed` retest leaves the status alone, since a run that cannot
  start says nothing about the claim.
- Needs: the experiment-vault skill and `vault` set in `research.yaml`. A node with no
  capsule cannot be retested from a record; the flow suggests `/research run` and stops.
- Definition: [references/retest.md](../skills/research/references/retest.md).

## research reconcile

`/research reconcile`. Was `aar-reconcile`.

Role: Reconciler. Is the result live?

- Invoke: `/research reconcile`, or "check whether our findings are in production".
- Does: seeds `adoption` blocks (`--migrate`), triages each node's adoption state by
  reading the source, binds a verification predicate to every `adopted`, `partial` or
  `contradicted` node with `dag_update.py --action adopt`, runs the predicates, and reports
  drift by kind. It proposes no fixes; each finding becomes a work item afterwards.
- Tool: `scripts/reconcile.py`, which exits non-zero on drift so it can gate a merge or run
  on a schedule; see [commands](commands.md#research-scriptsreconcilepy).
- References: [finding-kinds.md](../skills/research/references/finding-kinds.md),
  [adoption and drift](adoption-and-drift.md).
- Definition: [references/reconcile.md](../skills/research/references/reconcile.md).

## research housekeep

`/research housekeep`. Was `aar-housekeep`.

Role: Housekeeper. Keeps what everyone reads true.

- Invoke: `/research housekeep`, or "refresh the research dashboard".
- Does: syncs node statuses, regenerates the node index, runs `vault.py coverage --verify`
  when a vault is configured (result nodes with no capsule, and any recorded capsule that
  fails verification, both reported to you, never repaired), runs
  `validate_dag_references.py` and adds any orphaned ids to the DAG, regenerates the
  dashboard, and checks the deliverable links resolve.
- Definition: [references/housekeep.md](../skills/research/references/housekeep.md).

## research-dag

The DAG and its tools, a skill of its own again in 4.0.0 (it was folded into `research` in
3.0.0, where `/research dag` named it). `/research dag` now points here.

The engine. No workflow of its own: the flows decide what to do and call these tools to do
it. An agent without `research` can use them directly, as the [quick start](quick-start.md)
does. It needs no `work` skill.

- Invoke: any flow that changes the DAG, or "add a node", "rebuild the node index", "share
  this DAG in a store".
- Tools: `dag_update.py` (the only way to change the DAG, including `--action append` to
  add one item to a list field such as `capsules`), `generate_node_index.py`,
  `generate_dashboard.py`, `validate_dag_references.py`, `branch_manager.py`,
  `dag_store.py`, and `rms_config.py`, the shared `research.yaml` loader. See
  [commands](commands.md#research-dag-tools). The old paths under `research/bin/` still
  run them, with a note, until research 5.0.0.
- Asset: [`research.yaml.example`](../skills/research-dag/assets/research.yaml.example), the
  same file as the research skill's, which `/research start` and `/research init` copy to
  the workspace root when it has no `research.yaml`.
- Schemas: [`cli_schemas.json`](../skills/research-dag/schemas/cli_schemas.json) describes
  the tools' arguments for agents that call them programmatically;
  [`dag_event.schema.json`](../skills/research-dag/schemas/dag_event.schema.json) is the
  store's event format.
- References: [the tools](../skills/research-dag/references/tools.md),
  [the shared DAG store](../skills/research-dag/references/dag-store.md), and
  [the node schema](../skills/research-dag/references/node-schema.md): the fields a node
  carries, the status vocabulary, and the `capsules` field that makes a result
  reproducible.
- Definition: [SKILL.md](../skills/research-dag/SKILL.md).

## experiment-vault

Keeps every hypothesis experiment as a self-contained, immutable capsule in a Google Cloud
Storage bucket or a folder, so any later agent can restore it and run it again. New in 4.0.0.
Usable without the rest of AAR: with no `research.yaml`, pass `--vault` and `--project`.

- Invoke: `/research run`, `sync`, `audit`, `retest` and `housekeep` call it when a vault is
  configured; ask for it directly with "run this experiment for H-001 and keep it",
  "reproduce the result of H-001", "does H-001 still hold with numpy 2.1".
- Does: `vault.py run` runs the command and keeps the exact code at its commit (checked
  against the commit's git tree), the data it read, the Python environment and optionally
  every wheel, the hardware, the command, its seeds, the console output, the outputs and
  the metrics, then appends the capsule to the node's `capsules` through research-dag.
  `vault.py replay` restores a capsule into a fresh environment, runs it again and says
  whether the result is `identical`, `reproduced` within tolerance, `drifted` or `failed`.
- Tool: `vault.py`, with `init`, `run`, `capture`, `list`, `show`, `verify`, `restore`,
  `replay`, `coverage` and `lifecycle`; see [commands](commands.md#experiment-vault-tools).
- Settings: `vault.uri`, `vault.project` (or `dag_project`), `vault.vendor_wheels`,
  `vault.rtol` and `vault.atol` in `research.yaml`, or `RESEARCH_VAULT` and
  `RESEARCH_VAULT_PROJECT`; see [configuration](configuration.md#the-experiment-vault).
- Rules: commit before you run; never record secrets; never delete, overwrite or edit
  anything in the vault, since a wrong capsule is superseded by a new one with a `--note`;
  a replay that drifts is a finding, not an error to retry away.
- Leaves: blobs and manifests in the vault, and a `capsules` entry on the node for each run
  and retest.
- References: [capturing](../skills/experiment-vault/references/capturing.md),
  [replaying and retesting](../skills/experiment-vault/references/replaying.md),
  [storage](../skills/experiment-vault/references/storage.md) (the bucket, cost, archive
  classes, a local vault) and
  [the capsule format](../skills/experiment-vault/references/capsule-format.md); the
  manifest's [JSON Schema](../skills/experiment-vault/schemas/capsule.schema.json).
- Definition: [SKILL.md](../skills/experiment-vault/SKILL.md).

## literature-discovery

Finds what has been published on a question and the best published result. Usable
without the rest of AAR: it needs no `research.yaml`.

- Invoke: `/literature-discovery`, or "find the state of the art for ...".
- Tools: `openalex_discovery.py` (breadth, by relevance), `s2_ranking.py` (ranked by
  influential citations), `sota_baseline.py` (a baseline file from the top-ranked paper);
  see [commands](commands.md#literature-discovery-tools).
- Settings: `OPENALEX_EMAIL`, `S2_API_KEY`; see
  [configuration](configuration.md#environment-variables).
- Its own `requirements.txt` makes it installable alone:
  `pip install -r <skills>/literature-discovery/requirements.txt`.
- Definition: [SKILL.md](../skills/literature-discovery/SKILL.md).
