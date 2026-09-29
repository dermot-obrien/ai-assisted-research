---
name: research-dag
description: The hypothesis DAG engine that the research skills share. Adds, updates, relinks and adopts nodes in the hypothesis DAG safely, optionally in a shared event-sourced store that several machines and agents write to at once, recomputes the node index with parent-resolved readiness, regenerates the research dashboard, validates that nothing references a hypothesis that does not exist, and opens research branches. Use when a research skill needs to change or read the DAG, or when asked to add a node, rebuild the node index or dashboard, check the DAG's references, or share, import, pull or prune a DAG in a DAG store.
license: CC-BY-4.0 AND Apache-2.0. Instructions under CC BY 4.0, code under Apache-2.0; see the repository's LICENSE.
compatibility: Python 3.10 or newer with PyYAML, and git for a shared DAG store. Reads research.yaml, found by searching upward from the working directory, for the DAG, node index, work items and dashboard paths, and the optional DAG store.
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
| `dag_store` | Optional. A shared DAG store: a clone's path, or a git URL or bare repository to clone |
| `dag_project` | Optional. This project's folder in the store |

Paths are relative to the directory holding `research.yaml`. A new workspace starts from [assets/research.yaml.example](assets/research.yaml.example).

## The shared DAG store

With `dag_store` and `dag_project` both set, the DAG lives in a separate git repository as append-only event files, one folder per project, so several machines and agents can change it at once without merge conflicts. `dag_update.py` pulls the store, writes the change as events, pushes with a retry when someone else pushed first, and regenerates the YAML at `dag_path` from the replay. That YAML becomes a generated view, and every tool that reads it works unchanged. With neither key set, everything works on the plain YAML file as before.

When two writers change the same field at once, the later one wins and the view and `dag_store.py report` show the value it replaced. When two add a node under the same id, the one already in the store keeps it and the other takes a letter suffix (H-204.4.25b), recorded as an alias that `validate_dag_references.py` reports. [references/dag-store.md](references/dag-store.md) has the event format and the whole workflow.

## Tools

| Task | Command |
|---|---|
| Add a node under a parent | `python <skills>/research-dag/bin/dag_update.py --action add --parent H-001 --hypothesis "..." --target 0.05` |
| Update a node's status or result | `python <skills>/research-dag/bin/dag_update.py --action update --node-id H-001 --status validated --performance 0.07` |
| Record whether a node was adopted | `python <skills>/research-dag/bin/dag_update.py --action adopt --node-id H-001 --adoption adopted --artefact <path> --verification "<command>"` |
| Move a node under another parent | `python <skills>/research-dag/bin/dag_update.py --action relink --node-id H-001.2 --parent H-003` |
| Set any other field, or add a note | `python <skills>/research-dag/bin/dag_update.py --action set --node-id H-001 --field evidence --value "..."`, or `--action note --node-id H-001 --note "..."` |
| Seed a store project from an existing DAG | `python <skills>/research-dag/bin/dag_store.py import --from research/hypothesis-dag.yaml` |
| Pull the store and regenerate the view | `python <skills>/research-dag/bin/dag_store.py view` |
| Show concurrent edits and aliases | `python <skills>/research-dag/bin/dag_store.py report` |
| Record edits a tool made to the view directly | `python <skills>/research-dag/bin/dag_store.py record` |
| Archive the events of closed nodes | `python <skills>/research-dag/bin/dag_store.py prune --days 90` |
| Recompute the node index | `python <skills>/research-dag/bin/generate_node_index.py` |
| Regenerate the dashboard | `python <skills>/research-dag/bin/generate_dashboard.py` |
| Check every hypothesis reference resolves | `python <skills>/research-dag/bin/validate_dag_references.py` |
| Open a research branch, or hand a node over | `python <skills>/research-dag/bin/branch_manager.py --action init --node-id H-001 --topic <topic>` |

Each tool prints its full options with `--help`. `schemas/cli_schemas.json` describes the tools' arguments for agents that call them programmatically.

## Rules

Change the DAG only through `dag_update.py`, never by editing the YAML by hand: it keeps identifiers, parents and statuses consistent. Recompute the node index after any change to the DAG, since the research skills read readiness from the index rather than walking the DAG.

With a DAG store, the view is regenerated on every write, so an edit made to it directly is lost unless `dag_store.py record` turns it into events first. Run `dag_store.py view` before reading the DAG when others may have written since, and report the id `dag_update.py` prints for a new node, which may carry a suffix.
