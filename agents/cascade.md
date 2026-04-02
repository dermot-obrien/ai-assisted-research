# Agent: Cascade Analysis

**Objective**: When a breakthrough occurs, identify all hypothesis nodes whose assumptions may have changed and update their priorities.

**Trigger**: Automatically invoked by `/log-experiment` when an experiment is marked as a breakthrough, or by `/sync-research-result` when a node moves to `validated` or `ineffective`.

**Command**: `/cascade {node_id}` (can also be invoked manually)

---

## Protocol

### Step 1: Identify the Breakthrough
1. Read the node's `actual_performance` and `evidence`.
2. Extract the **key assumption change**: What did we believe before that is now different?
3. State it explicitly: "Before: X. Now: Y."

### Step 2: Scan for Affected Nodes
For each node in the hypothesis DAG, check if it might be affected:

1. **Evidence-based scan**: Search all nodes' `evidence`, `notes`, and `hypothesis` text for keywords related to the changed assumption.
2. **Parent/sibling scan**: Check sibling nodes (same parent) — if one sibling is validated, does it change the others?
3. **Contradiction scan**: Check `ineffective` nodes — could the breakthrough flip any of them?
4. **Unblock scan**: Check `pending` nodes whose parent is now `validated` — these move to the `ready` queue.

### Step 3: Classify Effects
For each affected node, classify the effect:

| Effect | Meaning | Findings Graph Edge | Action |
|--------|---------|--------------------| --------|
| **strengthens** | Breakthrough increases confidence this node will succeed | `strengthens` | Elevate priority in ready queue |
| **weakens** | Breakthrough decreases confidence | (no edge — note in DAG) | Lower priority |
| **contradicts** | Breakthrough contradicts this node's premise | `contradicts` | Add caveat to evidence, consider `ineffective` |
| **unblocks** | Breakthrough removes a blocker | `unblocks` | Move to `ready` queue |
| **elevates** | Breakthrough makes this node more valuable to pursue | `strengthens` | Mark as golden path |
| **supersedes** | Breakthrough makes this node's approach obsolete | `supersedes` | Mark as `discarded` |

### Step 4: Update Artifacts
1. **Add cascade effects** to `breakthroughs.yaml` under the triggering breakthrough.
2. **Add findings edges** to `findings-graph.yaml` for each relationship.
3. **Update node index** with new priorities (golden_path flags).
4. **Log the cascade** as a deliverable in the work item.

### Step 5: Report
Print a summary table:
```
CASCADE ANALYSIS for [breakthrough title]
Assumption changed: [before] -> [now]

  H-103  contradicted  Flat pipeline finding only applies to anomaly detection
  H-504  elevated      Directed GNN with parent bounds may work for forecasting
  H-301  strengthened   Domain generalisation makes classification more plausible
  H-211  unblocked     GIFS forecasting head now exists
```

---

## When NOT to Cascade
- Incremental improvements (not breakthroughs) — don't cascade
- If the experiment fails — don't cascade
- If the metric improvement is < target_improvement and the finding doesn't change assumptions — don't cascade

## Model Leeway
The cascade scan requires understanding research context — the agent should use its reasoning to identify non-obvious connections, not just keyword matching. The agent is encouraged to over-identify (flag more nodes for review) rather than under-identify (miss affected nodes).
