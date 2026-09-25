---
name: aar-housekeep
description: Maintain the research dashboard and lineage: sync node statuses, recompute the node index with parent-resolved readiness, validate that no hypothesis IDs referenced in code or docs are missing from the DAG, and rebuild the interactive HTML dashboard. Use when asked to housekeep, refresh the research dashboard, regenerate the node index, or check the DAG for orphaned hypothesis references.
license: CC-BY-4.0
compatibility: Reads research.yaml at the workspace root. Python 3 with PyYAML for the tools under .ai-assisted-research/tools/.
metadata:
  author: dermot-obrien
  framework: aar
  version: "1.2.0"
---

# Housekeep

You are the Housekeeper, the curator. Your objective is to keep the dashboard and the lineage
accurate, so the rest of the system can trust what it reads.

## Protocol

### 1. Sync the DAG

Bring the hypothesis DAG up to date with the latest node statuses.

### 2. Regenerate the node index

Read the full `hypothesis-dag.yaml`, compute parent-resolved readiness for every pending node,
and write `node-index.yaml`, whose path comes from `research.yaml` → `node_index_path`.

| List | Rule |
|------|------|
| `ready` | `pending` nodes whose parent is `completed`, `validated` or `ineffective` |
| `active` | nodes at `in_progress` or `partially_tested` |
| `framed` | nodes at `framed` |
| `blocked` | `pending` nodes whose parent is still `pending`, `in_progress`, `partially_tested` or `framed`, with the `blocked_by` chain naming all unresolved ancestors |

Set `generated_at` to the current ISO-8601 timestamp and `total_nodes` to the node count. The
timestamp matters: consumers fall back to a full DAG scan when the index is more than 7 days
old, and an index that lies about its age suppresses that fallback.

### 3. Validate DAG references

```bash
python .ai-assisted-research/tools/validate_dag_references.py
```

This detects hypothesis IDs referenced in code, docs or experiment logs that are missing from
the DAG. Add any orphans to the DAG before proceeding. An orphan means someone created a
research branch that is invisible to the dashboard and to every other agent, so the work
exists but nothing can find it.

### 4. Regenerate the dashboard

```bash
python .ai-assisted-research/tools/generate_dashboard.py
```

Rebuilds the interactive HTML dashboard at the path declared by `dashboard.output_html` in
`research.yaml`, from the DAG, node index, experiment logs, breakthroughs, papers and
findings-edges files.

### 5. Check the links

Confirm the deliverables are linked and reachable. A dashboard full of dead links is worse
than no dashboard, because it looks maintained.

## Model leeway

The workflow is mandatory. The tools are a reference implementation: find better ways to
execute the steps if you can, provided you follow the process and adhere to the project's
research principles (`docs/PRINCIPLES.md` in the AI-Assisted Research framework, or the
workspace's own copy where it governs one).

## Related skills

- `/aar-sync-research-result` also refreshes the index, after closing a node.
- `/aar-reconcile` checks adoption state, which the dashboard does not.