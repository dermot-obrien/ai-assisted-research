---
name: research
description: "Run research as a hypothesis DAG: baseline the state of the art and design the DAG, reconstruct the lineage of research that predates it, add or revise hypotheses, pick the next ready node, design one node's experiment as a work item, run it on its own branch, record the result back in the DAG, audit a result in a clean room, check results are live in the running system, and keep the node index and dashboard current. Use when asked to start or resume research, frame, run or sync a hypothesis, update the research lineage, audit or reconcile a research result, housekeep the research dashboard, or change the DAG; also answers to the retired names aar-start-research, aar-init-research, aar-update-lineage, aar-progress-research, aar-start-hypothesis, aar-progress-hypothesis, aar-sync-research-result, aar-run-audit, aar-reconcile, aar-housekeep and research-dag."
license: CC-BY-4.0 AND Apache-2.0. Instructions under CC BY 4.0, code under Apache-2.0; see the repository's LICENSE.
compatibility: Reads research.yaml at the workspace root. Python 3.10 or newer with PyYAML, and git for a shared DAG store or research branches. The start, frame, run, progress and sync flows hand the work item to the work skill (/work start, /work progress, /work initiative), so work must be installed for them; the start flow uses literature-discovery when it is installed.
metadata:
  author: dermot-obrien
  version: "3.1.0"
  homepage: https://github.com/dermot-obrien/ai-assisted-research
  x-skill-requires: "pkg:generic/dermot-obrien/ai-assisted-work/work ^3.0.0"
---

# Research

Research held as a hypothesis DAG in plain files, so every agent and person reads the same state. Each node is a measurable variant against the state of the art; a node is framed, run and synced, and its result decides what becomes ready next.

This skill was eleven skills (`aar-start-research`, `aar-start-hypothesis` and the rest, with `research-dag` as their engine). They ran the same tools over the same files, so none worked without the others; they are now flows of one skill.

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
| `/research audit <node>`, "audit", "verify a result" | Re-run the benchmark in a clean room and check the claims agree | [references/audit.md](references/audit.md) |
| `/research reconcile`, "is the research live", "check adoption" | Check the running system embodies what the research established | [references/reconcile.md](references/reconcile.md) |
| `/research housekeep`, "refresh the dashboard", "regenerate the node index" | Sync statuses, recompute the index, check references, rebuild the dashboard | [references/housekeep.md](references/housekeep.md) |
| `/research dag`, or any flow that changes the DAG | The DAG tools every flow uses, and the optional shared DAG store | [references/dag.md](references/dag.md) |

Read the flow's reference before acting, and the references it names when it names them. With no flow named and no DAG yet, start with `/research start`; with a DAG, `/research progress`.

## Rules that hold in every flow

1. Change the DAG only through the tools in `bin/` ([references/dag.md](references/dag.md)), never by editing the YAML or a store's events by hand, so every change is validated and every agent sees the same DAG.
2. A node's target is measured against the state of the art, with the source cited. A result without its measurement is not a result.
3. Audit against the baseline's evaluation, never the branch's own ([references/audit.md](references/audit.md)).
4. A flow that needs a work item asks the `work` skill for it and records the work item on the node. Without `work` installed, say so and stop rather than inventing a work item format.

## What is in this skill

| Folder | Holds |
|---|---|
| `bin/` | The DAG tools (`dag_update.py`, `dag_store.py`, `generate_node_index.py`, `generate_dashboard.py`, `validate_dag_references.py`, `branch_manager.py`) and the post-install check |
| `scripts/` | The flows' own tools: `discovery.py` (init), `audit_verify.py` (audit), `reconcile.py` (reconcile) |
| `references/` | One file per flow, and the shared `node-selection.md`, `finding-kinds.md`, `dag-store.md`, the research principles (`principles.md`) and how an inquiry becomes a hypothesis (`inquiry-seam.md`) |
| `assets/` | `research.yaml.example` and the run flow's output templates |
| `schemas/` | The tools' argument schemas and the DAG store's event schema |
