---
name: research-dag
description: "The hypothesis DAG and its tools: add, update, relink, adopt, set and append to nodes safely, optionally in a shared event-sourced store that several machines and agents write to at once; recompute the node index with parent-resolved readiness; regenerate the research dashboard; check that every hypothesis reference resolves; open research branches. Use when a research flow or an agent needs to change or read the DAG, or when asked to add a node, rebuild the node index or dashboard, check the DAG's references, or share, import, pull, report on or prune a DAG in a DAG store."
license: CC-BY-4.0 AND Apache-2.0. Instructions under CC BY 4.0, code under Apache-2.0; see the repository's LICENSE.
compatibility: Python 3.10 or newer with PyYAML, and git for a shared DAG store. Reads research.yaml, found by searching upward from the working directory (or $RMS_ROOT), for the DAG, node index, work items and dashboard paths, and the optional DAG store.
metadata:
  author: dermot-obrien
  version: "2.2.0"
  homepage: https://github.com/dermot-obrien/ai-assisted-research
  x-skill-requires: ""
---

# Research DAG

The hypothesis DAG in plain files, and the only tools that change it. Each node is a measurable claim with a parent it builds on; the DAG is the lineage of what was tried and what it showed. This skill owns the DAG's operations, so every flow, agent and machine changes and reads it the same way. It has no workflow of its own: the `research` skill decides what to do and calls these tools, and an agent without `research` can use them directly.

`<skills>` below is the directory the skills are installed in, so the tools are under `<skills>/research-dag/bin/`.

## Read

| For | Read |
|---|---|
| The workspace keys, every tool and its command, and the rules | [references/tools.md](references/tools.md) |
| The shared DAG store: opting in, seeding, concurrent writers, ids, pruning and the event format | [references/dag-store.md](references/dag-store.md) |
| The fields a node carries, the status vocabulary, and the fields that make a result reproducible | [references/node-schema.md](references/node-schema.md) |

## Rules

1. Change the DAG only through `bin/dag_update.py` (or `bin/dag_store.py record` after a tool edited the view), never by editing the YAML or a store's events by hand, so every change is validated and every agent sees the same DAG.
2. With a DAG store, run `dag_store.py view` before reading the DAG when others may have written since, and report the id `dag_update.py` prints for a new node, which may carry a suffix.
3. Recompute the node index after any change to the DAG (`generate_node_index.py`), since flows read readiness from the index rather than walking the DAG.
4. Add to a list field (notes, avenues, capsules) with `--action note` or `--action append`, never by setting the whole list, so concurrent writers' items all survive.

## What is in this skill

| Folder | Holds |
|---|---|
| `bin/` | `dag_update.py`, `dag_store.py`, `generate_node_index.py`, `generate_dashboard.py`, `validate_dag_references.py`, `branch_manager.py`, the shared `rms_config.py`, and the post-install check |
| `references/` | The tools, the DAG store, and the node schema |
| `schemas/` | The tools' argument schemas and the DAG store's event schema |
| `assets/` | `research.yaml.example`, the workspace file the tools read |
