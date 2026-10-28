---
name: research
description: "Run research as a hypothesis DAG: baseline the state of the art and design the DAG, reconstruct the lineage of research that predates it, add or revise hypotheses, pick the next ready node, design one node's experiment as a work item, run it on its own branch with every measured run kept as a replayable capsule, record the result back in the DAG, audit a result in a clean room, retest a result after a library, data or code change, check results are live in the running system, and keep the node index and dashboard current. Use when asked to start or resume research, frame, run, sync or retest a hypothesis, update the research lineage, audit or reconcile a research result, or housekeep the research dashboard; also answers to the retired names aar-start-research, aar-init-research, aar-update-lineage, aar-progress-research, aar-start-hypothesis, aar-progress-hypothesis, aar-sync-research-result, aar-run-audit, aar-reconcile and aar-housekeep."
license: CC-BY-4.0 AND Apache-2.0. Instructions under CC BY 4.0, code under Apache-2.0; see the repository's LICENSE.
compatibility: Reads research.yaml at the workspace root. Python 3.10 or newer with PyYAML, and git. Changes the DAG through the research-dag skill and keeps experiments through the experiment-vault skill, both installed beside it. The start, frame, run, progress and sync flows hand the work item to the work skill (/work start, /work progress, /work initiative), so work must be installed for them; the start flow uses literature-discovery when it is installed.
metadata:
  author: dermot-obrien
  version: "4.2.0"
  homepage: https://github.com/dermot-obrien/ai-assisted-research
  x-skill-requires: "pkg:generic/dermot-obrien/ai-assisted-work/work ^3.0.0, pkg:generic/dermot-obrien/ai-assisted-research/research-dag ^2.2.0, pkg:generic/dermot-obrien/ai-assisted-research/experiment-vault ^1.4.0"
---

# Research

Research held as a hypothesis DAG in plain files, so every agent and person reads the same state. Each node is a measurable variant against the state of the art; a node is framed, run and synced, and its result decides what becomes ready next. Every measured run is kept as a capsule in the experiment vault, so any result can be replayed, audited and retested later.

This skill is the method: the flows. It stands on two skills of the same bundle that also work without it: `research-dag`, which owns the DAG and the only tools that change it, and `experiment-vault`, which keeps and replays experiments. `literature-discovery` searches the literature.

## The flows

| The user | Flow | Read |
|---|---|---|
| `/research start <problem>`, "start a research project", "baseline the state of the art" | Baseline the state of the art, design the DAG, create the initiative and root work item | [references/start.md](references/start.md) |
| `/research init`, "reconstruct the research lineage", "bootstrap research onto this repository" | Reconstruct the lineage of ideas in a repository whose research predates the DAG | [references/init.md](references/init.md) |
| `/research lineage`, "add a hypothesis", "revise the DAG" | Add or update nodes, placed under the parents they depend on | [references/lineage.md](references/lineage.md) |
| `/research progress`, "continue the research", "what node is next" | Pick the next ready node and drive it through frame and run | [references/progress.md](references/progress.md) |
| `/research frame <node>`, "frame", "design the experiment for" a node | Design one node's experiment as a work item; the node moves to framed | [references/frame.md](references/frame.md) |
| `/research run <node>`, "run", "execute" a framed node | Run the experiment on its own branch, a finding per activity | [references/run.md](references/run.md) |
| `/research sync <node>`, "record the result", "close out a hypothesis" | Return the work item's result to the DAG: validated, ineffective or discarded | [references/sync.md](references/sync.md) |
| `/research audit <node>`, "audit", "verify a result" | Replay the capsule, re-run the benchmark in a clean room and check the claims agree | [references/audit.md](references/audit.md) |
| `/research retest <node> [what changed]`, "does it still hold", "reproduce" a prior result | Replay a node's capsule under a library, data or code change, and record whether it held | [references/retest.md](references/retest.md) |
| `/research reconcile`, "is the research live", "check adoption" | Check the running system embodies what the research established | [references/reconcile.md](references/reconcile.md) |
| `/research pool`, "put the hypotheses on the board", "run the pool", "pick up a hypothesis" | Offer every node that may start to a pool of agents on any platform; a worker takes one, runs it and closes it; a held node locks its chain | [references/pool.md](references/pool.md) |
| `/research campaign <id>`, "retest everything", "check the whole tree reproduces" | Retest every result from the root down, one node per agent, within a time box, recording reproduced, rebuilt, differs or unverifiable | [references/pool.md](references/pool.md#a-retest-campaign) |
| `/research housekeep`, "refresh the dashboard", "regenerate the node index" | Sync statuses, recompute the index, check references, rebuild the dashboard | [references/housekeep.md](references/housekeep.md) |
| `/research dag`, or any flow that changes the DAG | The DAG tools every flow uses, and the optional shared DAG store | The research-dag skill: [tools](../research-dag/references/tools.md), [node schema](../research-dag/references/node-schema.md) |

Read the flow's reference before acting, and the references it names when it names them. With no flow named and no DAG yet, start with `/research start`; with a DAG, `/research progress`.

## Rules that hold in every flow

1. Change the DAG only through the research-dag skill's tools ([tools](../research-dag/references/tools.md)), never by editing the YAML or a store's events by hand, so every change is validated and every agent sees the same DAG.
2. A node's target is measured against the state of the art, with the source cited. A result without its measurement is not a result.
3. Audit against the baseline's evaluation, never the branch's own ([references/audit.md](references/audit.md)).
4. With `vault` set in `research.yaml`, a result is the metric of a capsule: run every measured experiment through `vault.py run`, and record no result whose node names no capsule ([run](references/run.md), [sync](references/sync.md)). Never edit or delete anything in the vault.
5. A flow that needs a work item asks the `work` skill for it and records the work item on the node. Without `work` installed, say so and stop rather than inventing a work item format.

## What is in this skill

| Folder | Holds |
|---|---|
| `bin/` | The post-install check, and launchers that keep the DAG tools' old paths (`research/bin/dag_update.py` and the rest) working until 5.0.0; the tools are in research-dag |
| `scripts/` | The flows' own tools: `discovery.py` (init), `audit_verify.py` (audit), `reconcile.py` (reconcile), `pool.py` (pool and campaign) |
| `references/` | One file per flow, and the shared `node-selection.md`, `finding-kinds.md`, the research principles (`principles.md`) and how an inquiry becomes a hypothesis (`inquiry-seam.md`) |
| `assets/` | `research.yaml.example` and the run flow's output templates |
| `schemas/` | The flows' tools' argument schemas |
