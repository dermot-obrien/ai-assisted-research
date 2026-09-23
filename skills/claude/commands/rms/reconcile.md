# /reconcile

Check whether the running system embodies what the research established. Reports
the gap; proposes nothing.

`status` says whether a hypothesis is true. `adoption.state` says whether it is
live. This command is about the second.

## Instructions

**Read and follow exactly the full agent instructions at:**

`.ai-assisted-research/agents/reconciler.md`

## Quick reference

```bash
# Seed adoption blocks on a DAG that predates AAR 1.2.0
python .ai-assisted-research/tools/reconcile.py --dag research/hypothesis-dag.yaml --migrate

# Run the loop
python .ai-assisted-research/tools/reconcile.py --dag research/hypothesis-dag.yaml --cwd .

# Record a verdict
python .ai-assisted-research/tools/dag_update.py --action adopt --node-id H-001 \
  --adoption adopted --artefact "src/Thing.java" \
  --verification "grep -q 'thing = 0.02' src/Thing.java"
```

Exits non-zero on drift, so it can gate a merge or run on a schedule.
