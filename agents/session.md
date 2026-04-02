# Agent: Session Protocol

**Objective**: Define what happens at the start and end of every research session to ensure continuity across agents and time gaps.

---

## Session Start Protocol

When a human or agent begins a research session, the FIRST action is:

### 1. Read research.yaml
Locate all artifact paths. If `research.yaml` doesn't exist, run `/init-research`.

### 2. Show Dashboard
Regenerate and display the dashboard (or direct the user to open it):
```
python {framework}/tools/housekeeper.py --config research.yaml
```
If running in a terminal without a browser, print a text summary.

### 3. Print Session Briefing
```
SESSION BRIEFING
================
Nodes: 72 total (8 validated, 23 completed, 4 active, 24 pending, 6 ineffective)
Experiments: 23 logged
Breakthroughs: 7 recorded

GOLDEN PATH (highest priority):
  H-204.1.1  Autoregressive multi-step shard prediction
  H-204.1.2  Causal transformer with sufficient training budget
  H-701.1    Cross-channel GIFS (partially tested: 7.7% improvement)

RECENT BREAKTHROUGHS (last session):
  B7: Elapsed-time features — test ratio 0.556 (new best)

PENDING CASCADE EFFECTS:
  (none — all cascades resolved)

PAPERS IN PROGRESS:
  P-001: "Fractal Shard Forecasting..." (DRAFT) — 5 contributing nodes
```

### 4. Confirm Direction
Ask the user: "Continue with the golden path, or explore a different direction?"

---

## Session End Protocol

When a session is ending (user signs off, token budget low, or explicit end):

### 1. Generate Session Report
Create a session report capturing what happened:

```yaml
# sessions/session-YYYY-MM-DD-HHMM.yaml
session_id: "2026-04-02-1000"
agent: "claude-opus-4-6"
duration_hours: 8
experiments_run: [18, 19, 20, 21, 22, 23]
nodes_updated:
  - id: H-204.1.4
    change: "pending -> validated"
    result: "test ratio 0.556"
  - id: H-701.1
    change: "pending -> partially_tested"
    result: "7.7% relative improvement"
breakthroughs: [B7]
cascades_triggered: 0
deliverables_written: [D06, D07, D08, D09]
papers_updated: [P-001]
recommendations:
  - "Run H-204.1.1 (autoregressive multi-step) — highest expected impact"
  - "Reconcile H-701.1 normalization with PhysioNet baseline"
  - "Consider H-301 (UCR classification) — elevated by domain generalisation finding"
```

### 2. Commit Session Report
```bash
git add sessions/
git commit -m "session: {date} — {n_experiments} experiments, {n_breakthroughs} breakthroughs"
```

### 3. Regenerate Dashboard
Run `/housekeep` to ensure the dashboard reflects the final state.

### 4. Print Handoff Summary
Print a concise summary for the next session:
```
SESSION ENDED
=============
Key results: H-204.1.4 validated (0.556), H-701.1 partially tested (7.7%)
New best: test ratio 0.556 (elapsed-time features)
Next recommended: H-204.1.1 (autoregressive multi-step)
Dashboard: autoresearch/dashboard.html
```

---

## Storage

Session reports are stored in a `sessions/` directory at the project root.
Each session is one YAML file named by date-time.

The session directory is referenced in `research.yaml`:
```yaml
sessions_path: "sessions/"
```

---

## Model Leeway

The session protocol is MANDATORY at session boundaries. The agent may format the briefing and report as appropriate for the interface (terminal, web, IDE). The content — what was done, what was found, what's next — must always be present.
