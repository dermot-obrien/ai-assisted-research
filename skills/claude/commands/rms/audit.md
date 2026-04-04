# Command: /audit

**Purpose**: Request an independent review of a specific hypothesis node or experiment result. Use this when you suspect a conclusion may be invalid, overstated, or methodologically flawed.

**Usage**:
```
/audit H-204.3.9.5
/audit experiment 75
/audit H-204.3.9 --scope methodology
```

---

## For the Person Requesting the Audit

Give the auditor this instruction:

> Review the research finding at **{node_id}** (or experiment **{experiment_id}**). The hypothesis DAG, experiment log, and all source code are in this repository. Your role is to independently verify or contest the claimed results. You are NOT the agent that produced these results — your value is fresh eyes with no investment in the outcome.

Then point them to:
1. This file (`.ai-assisted-research/skills/claude/commands/rms/audit.md`) — the full protocol
2. The hypothesis DAG (`research.yaml` → `dag_path`) — where results are recorded
3. The experiment log (`research.yaml` → `dashboard.experiment_log`) — detailed experiment records

---

## For the Auditor

### Step 1: Locate the Target

Read `research.yaml` in the workspace root. It points to all artifacts:

```yaml
dag_path: ".irregular-timeseries-intent/change/work-items/WI-032-.../D01-hypothesis-dag.yaml"
dashboard:
  experiment_log: "autoresearch/experiments/experiment-log.jsonl"
  breakthroughs: "autoresearch/breakthroughs.yaml"
```

Find the node or experiment you've been asked to review:
- **By node**: Search the DAG file for `id: {node_id}`. Read its `hypothesis`, `actual_performance`, `evidence`, and `notes`.
- **By experiment**: Search the experiment log for `"experiment_id": {N}`. Read its `hypothesis`, `metric_value`, `notes`, and `node_id`.

### Step 2: Understand the Claim

Before examining code, understand what is being claimed:
- What metric was reported? (e.g., "60.3% overall accuracy")
- On what data? (e.g., "20 stocks, 22 days minute bars")
- Using what methodology? (e.g., "separate causal trees, 60-bar embargo, single-position trading")
- What is the baseline? (e.g., "33.3% random for 3-class classification")

### Step 3: Examine the Code

Find the code that produced the result. The experiment log entry and DAG node should reference the relevant files. Common locations:
- `autoresearch/train_channel_segment.py` — the main experiment file
- `autoresearch/generate_predictions.py` — prediction generator (model side)
- `autoresearch/evaluate_predictions.py` — independent evaluator (evaluation side)
- `python/irregular_timeseries/gifs/` — tree builder and segmenter

**Check for these issues (in priority order):**

#### A. Data Leakage (Critical)
- [ ] Are raw bars split by time BEFORE any feature computation?
- [ ] Is there an embargo gap (>= prediction horizon) between train and test?
- [ ] Are trees/models built SEPARATELY per split (no shared state)?
- [ ] Can a feature at time T contain information from time T+1 or later?
- [ ] Are labels computed within-split only (no cross-split price references)?

#### B. Evaluation Integrity (Major)
- [ ] Is accuracy computed on ALL predictions (not a filtered subset)?
- [ ] Is the trading simulation realistic (single position, capital constraints)?
- [ ] If there's an independent evaluator, does it share ANY code with the model?
- [ ] Are the evaluation metrics clearly defined and reported?

#### C. Methodology (Major)
- [ ] Is the train/val/test split temporal (not random)?
- [ ] Is the test set large enough for statistical significance?
- [ ] Are random seeds fixed for reproducibility?
- [ ] Can the experiment be reproduced from the committed code?

#### D. Code Quality (Medium)
- [ ] Are all code paths exercised?
- [ ] Are there undefined variables or dead code?
- [ ] Does the implementation match the documented methodology?

### Step 4: Record Your Findings

For each issue found, add an entry to the node's `audit_findings` array in the hypothesis DAG:

**File**: The DAG file path from `research.yaml` → `dag_path`
**Location**: Inside the node you audited, add or append to `audit_findings:`

```yaml
  audit_findings:
    - noted_in_experiment: null
      severity: critical      # critical | major | medium
      source: auditor
      finding: "One-line description of the issue"
      auditor_notes: |
        Your detailed verbatim notes. Include:
        - What you examined (file, line number, commit hash)
        - What you found (the specific issue)
        - Why it matters (impact on claimed results)
        - What a valid fix would look like
      resolution: null
      resolved_by_experiment: null
```

### Step 5: Set Status if Warranted

If your findings are severe enough to call the results into question:

```yaml
  status: contested    # was: validated
```

The `contested` status means:
- The results are unreliable until remediated
- Child nodes are blocked until the contest is resolved
- The dashboard shows a ⚠ warning icon
- The node can return to `validated` after remediation

Valid transitions: `validated → contested → validated | ineffective | in_progress`

### Step 6: Check for Cascade Effects

Do your findings affect other nodes?
- **Children** that depend on this node's results
- **Siblings** that use the same methodology
- **Parents** whose evidence cites this node

If yes, note the cascade in `autoresearch/breakthroughs.yaml`:

```yaml
  - id: B{next}
    experiment_id: null
    node_id: {audited_node}
    title: "AUDIT: {short description}"
    description: "..."
    impact: "..."
    date: "{today}"
    cascade_effects:
      - node_id: {affected_node}
        effect: weakened|contradicted|contested
        explanation: "..."
```

### Step 7: Regenerate Dashboard

```bash
python autoresearch/generate_dashboard.py
```

Contested nodes will appear with orange dashed borders and ⚠ icons.

### Step 8: Commit

```bash
git add -A
git commit -m "audit({node_id}): {one-line summary of findings}"
```

---

## Severity Guide

| Severity | Meaning | Example | Action |
|----------|---------|---------|--------|
| **critical** | Invalidates the claimed result | Future data leakage in features | Set status to `contested` |
| **major** | Materially affects the result | Unrealistic P&L simulation | Add finding, consider `contested` |
| **medium** | Methodological concern | Untested code path, missing error handling | Add finding, note for remediation |

---

## What NOT to Do

- **Don't modify model code** — your role is analytical, not implementation
- **Don't re-run experiments** — point out what needs fixing, let the experimenter fix it
- **Don't change results** — add findings alongside existing results, don't overwrite
- **Don't block silently** — always record your findings even if you're unsure

---

## Quick Reference

| What | Where |
|------|-------|
| Research signpost | `research.yaml` (workspace root) |
| Hypothesis DAG | Path in `research.yaml` → `dag_path` |
| Experiment log | Path in `research.yaml` → `dashboard.experiment_log` |
| Breakthroughs | Path in `research.yaml` → `dashboard.breakthroughs` |
| Node index | Path in `research.yaml` → `node_index_path` |
| Dashboard | `python autoresearch/generate_dashboard.py` → `autoresearch/dashboard.html` |
| Auditor agent spec | `.ai-assisted-research/agents/auditor.md` |
| Auditor step-by-step | `docs/trading-system/auditor-instructions.md` |
| Evaluation methodology | `docs/trading-system/evaluation-methodology.md` |
