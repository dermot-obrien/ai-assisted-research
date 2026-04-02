# Agent: Log Experiment

**Objective**: Record an experiment result and sync it to the hypothesis DAG in one step.

This is the **most-used command in active research**. It replaces the manual 6-step process of updating experiment log, DAG, node index, progress.yaml, dashboard, and git commit.

**Command**: `/log-experiment {node_id} {metric_name}={value} "{hypothesis}"`

**Example**: `/log-experiment H-204.1.4 val_mse_ratio=0.556 "Elapsed-time features improve prediction"`

---

## Protocol

### Step 1: Validate Input
1. **Read `research.yaml`** to locate all artifact paths.
2. **Verify node exists** in the hypothesis DAG.
3. **Parse metric**: name and numeric value.

### Step 2: Append Experiment Log
1. Read `experiment-log.jsonl` to determine next experiment_id.
2. Create experiment record following `schemas/experiment.yaml`.
3. Set `improved = true` if metric_value is better than the node's current `actual_performance` (or if no prior performance exists).
4. Append JSON line to the experiment log.

### Step 3: Update Hypothesis DAG
If `improved`:
1. Update the node's `actual_performance` with the new metric.
2. Update `evidence` to include the experiment reference.
3. If node was `pending`, change status to `in_progress`.
4. If the result meets the node's `target_improvement`, consider changing to `validated`.

### Step 4: Check for Breakthrough
Ask the agent (or the user): **"Is this a breakthrough?"** — a result that changes research direction, not just an incremental improvement.

If YES:
1. Prompt for: title, description, impact.
2. Append to `breakthroughs.yaml` (or create it).
3. **Trigger cascade analysis** (see `agents/cascade.md`).

### Step 5: Regenerate Node Index
Run the node index regeneration logic:
- Recompute `ready`, `active`, `blocked` lists.
- Update `generated_at` timestamp.

### Step 6: Regenerate Dashboard
Run `/housekeep` to update the interactive dashboard.

### Step 7: Git Commit
Stage and commit all changed files with message:
```
experiment({node_id}): {hypothesis}

{metric_name}={metric_value} {'IMPROVED' if improved else 'no improvement'}
Experiment #{experiment_id}
```

---

## Flags

- `--breakthrough "{title}"` — Skip the breakthrough question, mark as breakthrough with given title.
- `--no-commit` — Don't auto-commit (useful when batching multiple experiments).
- `--diagnostic` — Mark as diagnostic experiment (no metric value expected).

## Model Leeway

The agent implements the steps directly using file reads/writes and git commands. The output must match the `schemas/experiment.yaml` schema and the DAG must be consistently updated. A `tools/log_experiment.py` script may be added in a future version for automation.
