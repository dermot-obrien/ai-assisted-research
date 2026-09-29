---
name: research-dag
description: The hypothesis DAG engine that the research skills share. Adds, updates and adopts nodes in the hypothesis DAG safely, recomputes the node index with parent-resolved readiness, regenerates the research dashboard, validates that nothing references a hypothesis that does not exist, and opens research branches. Use when a research skill needs to change or read the DAG, or when asked to add a node, rebuild the node index or dashboard, or check the DAG's references.
license: CC-BY-4.0 AND Apache-2.0. Instructions under CC BY 4.0, code under Apache-2.0; see the repository's LICENSE.
compatibility: Python 3.10 or newer with PyYAML. Reads research.yaml, found by searching upward from the working directory, for the DAG, node index, work items and dashboard paths.
metadata:
  author: dermot-obrien
  version: "1.1.0"
  homepage: https://github.com/dermot-obrien/ai-assisted-research
  x-skill-requires: ""
---

# Research DAG

The engine under the research skills. It owns the hypothesis DAG's operations, so every skill changes and reads the DAG the same way. It has no workflow of its own: the `aar-*` skills decide what to do and call these tools to do it.

`<skills>` below is the directory this skill is installed in, where the research skills sit beside it.

## The workspace

Every tool reads `research.yaml`, searching upward from the working directory, for:

| Key | What it is |
|---|---|
| `dag_path` | The hypothesis DAG, conventionally `research/hypothesis-dag.yaml` |
| `node_index_path` | The computed index of ready and blocked nodes |
| `work_items_path` | Where the work items for research nodes live |
| `dashboard.*` | The dashboard's inputs and its output HTML |

Paths are relative to the directory holding `research.yaml`. A new workspace starts from [assets/research.yaml.example](assets/research.yaml.example).

## Tools

| Task | Command |
|---|---|
| Add a node under a parent | `python <skills>/research-dag/bin/dag_update.py --action add --parent H-001 --hypothesis "..." --target 0.05` |
| Update a node's status or result | `python <skills>/research-dag/bin/dag_update.py --action update --node-id H-001 --status validated --performance 0.07` |
| Record whether a node was adopted | `python <skills>/research-dag/bin/dag_update.py --action adopt --node-id H-001 --adoption adopted --artefact <path> --verification "<command>"` |
| Recompute the node index | `python <skills>/research-dag/bin/generate_node_index.py` |
| Regenerate the dashboard | `python <skills>/research-dag/bin/generate_dashboard.py` |
| Check every hypothesis reference resolves | `python <skills>/research-dag/bin/validate_dag_references.py` |
| Open a research branch, or hand a node over | `python <skills>/research-dag/bin/branch_manager.py --action init --node-id H-001 --topic <topic>` |

Each tool prints its full options with `--help`. `schemas/cli_schemas.json` describes the tools' arguments for agents that call them programmatically.

## Rules

Change the DAG only through `dag_update.py`, never by editing the YAML by hand: it keeps identifiers, parents and statuses consistent. Recompute the node index after any change to the DAG, since the research skills read readiness from the index rather than walking the DAG.
