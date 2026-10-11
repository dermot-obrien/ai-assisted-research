<!--
SPDX-FileCopyrightText: 2026 Dermot O'Brien
SPDX-License-Identifier: CC-BY-4.0
-->

# Skills

The two skills and the research flows, what each does, when to use it, what it needs and what it leaves
behind. Each skill's `SKILL.md` is the definition the agent follows; this page is the
guide for people. Every skill ships the post-install check `bin/check.py`; see
[commands](commands.md#checkpy-every-skill).

Two skills. `research` is the whole method, one flow per row below, with the DAG tools they share. Until version 3.0.0 those flows were eleven skills, named in each section; the skill still answers to the old names. `literature-discovery` searches the literature and works on its own.

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
| [`/research reconcile`](#research-reconcile) | Check results are live in the running system | nothing else |
| [`/research housekeep`](#research-housekeep) | Refresh the index, references and dashboard | nothing else |
| [`/research dag`](#research-dag) | The DAG tools every flow calls | Python, PyYAML, git for a store |

| Skill | Use it to | Needs |
|---|---|---|
| [literature-discovery](#literature-discovery) | Search the literature, on its own or for a baseline | Python, requests, PyYAML, network |

"AAW" means AI-Assisted Work's `work` skill (`/work start`, `/work progress`,
`/work initiative`), 3.0.0 or later, installed in the same workspace. It replaced the five
`aaw-*` work skills in AI-Assisted Work 4.0.0. The exact version ranges are in
[`bundle.json`](../bundle.json).

A typical project runs them in this order: `/research start` (or `/research init`),
then for each node `/research frame`, `/research run`,
`/research sync`, with `/research audit` before or after the sync,
`/research lineage` whenever a new avenue appears, and `/research housekeep` and
`/research reconcile` from time to time.

## research start

`/research start`. Was `aar-start-research`.

Role: Specialist. Starts a research project from nothing.

- Invoke: `/research start {topic}`, or "start a research project on ...".
- Does: baselines the state of the art with `literature-discovery`, recording the best
  published result with its citation; turns the gap into measurable variants; proposes the
  DAG, each node with hypothesis, target, datasets and parent evidence; asks AAW for the
  initiative (`/work initiative`) and the root work item (`/work start`).
- Leaves: `research/hypothesis-dag.yaml`, an AAW initiative and root work item, and a
  signpost to where the research lives.
- Use `/research init` instead when the research already happened.
- Definition: [SKILL.md](../skills/research start/SKILL.md).

## research init

`/research init`. Was `aar-init-research`.

Role: Discovery. Brings AAR to a repository whose research predates it.

- Invoke: `/research init`, or "reconstruct the research lineage of this repository".
- Does: finds the kernel idea in early commits and docs, identifies major shifts as
  branches, cites a commit, pull request or file and line for every claim, confirms the
  lineage with you, then writes the DAG and sets up the AAW initiative and root work item.
  Where evidence is thin it marks nodes as inferred rather than guessing.
- Tool: `scripts/discovery.py [--confirm]` gathers first markers; see
  [commands](commands.md#research-scriptsdiscoverypy).
- Definition: [SKILL.md](../skills/research init/SKILL.md).

## research lineage

`/research lineage`. Was `aar-update-lineage`.

Role: Specialist. Extends the search space.

- Invoke: `/research lineage`, or "add a hypothesis that ...".
- Does: re-baselines if the state of the art has moved, formulates a specific, measurable
  variant, places it under the parents it truly depends on, records the evidence, and
  regenerates the node index. It pushes back on a node that cannot be measured.
- Tools: `research`'s `dag_update.py` and `generate_node_index.py`.
- Definition: [SKILL.md](../skills/research lineage/SKILL.md).

## research progress

`/research progress`. Was `aar-progress-research`.

Role: Worker. Drives a strand without you naming a node.

- Invoke: `/research progress`, or "continue the research".
- Does: picks the next node from the index's `ready` list (warning before working a
  `blocked` one), then runs the three phases through `/research frame`,
  `/research run` and `/research sync`.
- Reference: [node-selection.md](../skills/research progress/references/node-selection.md).
- Definition: [SKILL.md](../skills/research progress/SKILL.md).

## research frame

`/research frame`. Was `aar-start-hypothesis`.

The design phase for one node.

- Invoke: `/research frame {node_id}`.
- Does: checks the node is `ready` (or warns if `blocked`), extracts its hypothesis,
  targets, datasets and parent evidence, and asks `/work start` for a work item titled
  `{node_id}-research-{topic}`, classed as an intervention (or a change if local) so AAW
  does not route it back as an inquiry. Records the work item on the node and moves it to
  `framed`.
- Leaves: a work item with `scope.md`, `research.md` and `plan.md`, even if the experiment
  never runs.
- Definition: [SKILL.md](../skills/research frame/SKILL.md).

## research run

`/research run`. Was `aar-progress-hypothesis`.

The execution phase for one framed node.

- Invoke: `/research run {WI_id} {node_id}`.
- Does: on first run, checks the node is `framed`, creates `research/{node_id}-{topic}`,
  fixes `parent_performance` and `target_metric` in the work item's `metadata.yaml`, and
  moves the node to `in_progress`. Then hands the task loop to `/work progress`,
  recording a `finding` and `prompted_by` per activity. When the work item is done, writes
  the blog post and arXiv draft, or a pivot report, from
  [`assets/templates/`](../skills/research/assets/templates/), and calls
  `/research sync`.
- Definition: [SKILL.md](../skills/research run/SKILL.md).

## research sync

`/research sync`. Was `aar-sync-research-result`.

The return path from a finished work item to the DAG.

- Invoke: `/research sync {node_id} {WI_id}`.
- Does: checks the work item is `done` and the node `in_progress`; reads
  `actual_performance` from `metadata.yaml` and the latest finding from `progress.yaml`;
  sets the node to `validated` (met the target), `ineffective` (missed it) or `discarded`
  (stopped early); links the deliverables; commits; regenerates the index and dashboard.
  Where the node began as an AAW inquiry it proposes the hand-back: a delivery work item for
  a validated result, a closed lesson otherwise, and a decision record where the finding
  settles an architectural choice. It proposes; it does not open them unasked.
- If metrics are missing it tries to reconstruct them and otherwise leaves the node
  `in_progress` rather than invent a result.
- Definition: [SKILL.md](../skills/research sync/SKILL.md).

## research audit

`/research audit`. Was `aar-run-audit`.

Role: Auditor. Is the result sound?

- Invoke: `/research audit`, or "audit the result for H-001".
- Does: re-runs the benchmarks in a clean room, with evaluation scripts from `main`, never
  from the branch under audit; checks the code changes are clean; checks the data, the
  measured performance and the written claims agree. Reports what reproduced as well as
  what did not, and never changes the node's status itself.
- Tool: `scripts/audit_verify.py`; see [commands](commands.md#research-scriptsaudit_verifypy).
- Definition: [SKILL.md](../skills/research audit/SKILL.md).

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
- References: [finding-kinds.md](../skills/research reconcile/references/finding-kinds.md),
  [adoption and drift](adoption-and-drift.md).
- Definition: [SKILL.md](../skills/research reconcile/SKILL.md).

## research housekeep

`/research housekeep`. Was `aar-housekeep`.

Role: Housekeeper. Keeps what everyone reads true.

- Invoke: `/research housekeep`, or "refresh the research dashboard".
- Does: syncs node statuses, regenerates the node index, runs
  `validate_dag_references.py` and adds any orphaned ids to the DAG, regenerates the
  dashboard, and checks the deliverable links resolve.
- Definition: [SKILL.md](../skills/research housekeep/SKILL.md).

## research dag

`/research dag`. Was `research`.

The engine. No workflow of its own: the flows decide what to do and call these
tools to do it. You can also call them directly, as the [quick start](quick-start.md) does.

- Tools: `dag_update.py` (the only way to change the DAG), `generate_node_index.py`,
  `generate_dashboard.py`, `validate_dag_references.py`, `branch_manager.py`,
  `dag_store.py`, and `rms_config.py`, the shared `research.yaml` loader. See
  [commands](commands.md#the-research-skills-dag-tools).
- Asset: [`research.yaml.example`](../skills/research/assets/research.yaml.example),
  which the installer seeds.
- Schemas: [`cli_schemas.json`](../skills/research/schemas/cli_schemas.json) describes
  the tools' arguments for agents that call them programmatically;
  [`dag_event.schema.json`](../skills/research/schemas/dag_event.schema.json) is the
  store's event format.
- Reference: [the shared DAG store](../skills/research/references/dag-store.md).
- Definition: [SKILL.md](../skills/research/SKILL.md).

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
