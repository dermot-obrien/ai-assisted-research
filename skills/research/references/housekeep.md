# Housekeep

`<skills>` below is the directory the skills are installed in. The DAG tools this flow runs are in the research-dag skill, under `<skills>/research-dag/bin/`.

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

### 3. Check every result has a capsule

With `vault` set in `research.yaml`, run `python <skills>/experiment-vault/bin/vault.py coverage --verify`. It lists the result nodes with no capsule, and checks that every capsule the DAG names is in the vault, unchanged, with all its files. Report both; a capsule that fails verification is a finding for the user, never something to repair by rewriting the vault.

### 4. Validate DAG references

```bash
python <skills>/research-dag/bin/validate_dag_references.py
```

This detects hypothesis IDs referenced in code, docs or experiment logs that are missing from
the DAG. Add any orphans to the DAG before proceeding. An orphan means someone created a
research branch that is invisible to the dashboard and to every other agent, so the work
exists but nothing can find it.

### 5. Regenerate the dashboard

```bash
python <skills>/research-dag/bin/generate_dashboard.py
```

Rebuilds the interactive HTML dashboard at the path declared by `dashboard.output_html` in
`research.yaml`, from the DAG, node index, experiment logs, breakthroughs, papers and
findings-edges files.

### 6. Check the links

Confirm the deliverables are linked and reachable. A dashboard full of dead links is worse
than no dashboard, because it looks maintained.

## Model leeway

The workflow is mandatory. The tools are a reference implementation: find better ways to
execute the steps if you can, provided you follow the process and adhere to the project's
research principles ([principles.md](principles.md), or the workspace's own copy where it governs one).

## Related skills

- `/research sync` also refreshes the index, after closing a node.
- `/research reconcile` checks adoption state, which the dashboard does not.