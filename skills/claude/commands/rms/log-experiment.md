# /log-experiment

Record an experiment result and sync to the hypothesis DAG in one step.

**Usage**: `/log-experiment {node_id} {metric_name}={value} "{hypothesis}"`

**Example**: `/log-experiment H-204.1.4 val_mse_ratio=0.556 "Elapsed-time features improve prediction"`

**Flags**:
- `--breakthrough "{title}"` — Mark as breakthrough with cascade analysis
- `--no-commit` — Don't auto-commit
- `--diagnostic` — No metric value expected

**Agent**: See [`agents/log-experiment.md`](../../../../agents/log-experiment.md) for the full protocol.

**What it does** (in one step):
1. Appends to `experiment-log.jsonl`
2. Updates the hypothesis DAG node (status, actual_performance)
3. If breakthrough: appends to `breakthroughs.yaml` and triggers `/cascade`
4. Regenerates `node-index.yaml`
5. Regenerates dashboard
6. Git commits all changes
