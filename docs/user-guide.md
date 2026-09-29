# User guide

The full research cycle, step by step, for human researchers and the agents working with
them. It assumes AAR and AAW are installed in the workspace; the
[quick start](quick-start.md) does that and tries the tools on a two-node DAG. The
[concepts](concepts.md) page explains the terms used here.

Commands below run from the workspace root. `<skills>` is where the skills are installed,
usually `.agents/skills`. Slash commands are typed in your agent; you can also ask for the
same thing in plain words.

All research execution goes through AI-Assisted Work (AAW): AAR decides what to research
and records what was found, AAW runs the work.

---

## 0. Starting in an existing repository

When the research already happened before anyone recorded it, reconstruct the lineage
instead of starting fresh.

### Step 0.1: Run discovery

```text
/aar-init-research
```

The Discovery role scans early commits, READMEs and docs for the kernel idea and the major
shifts since, citing a commit, pull request or file and line for each. Its helper gathers
the first markers:

```bash
python <skills>/aar-init-research/scripts/discovery.py
```

It proposes H-000 (the original baseline) and H-001 (the current state) and asks before
writing `hypothesis-dag.yaml` in the current directory. Move that file to `dag_path`
(normally `research/hypothesis-dag.yaml`) if you accept it from the command line; the skill
writes it in the right place.

### Step 0.2: Confirm the lineage

Check the proposed nodes and their evidence. Correct anything guessed; a node marked as
inferred, with its reasoning, is better than one presented as established.

---

## 1. Starting a new research project

The Specialist role establishes what "better" means before anything is tried.

### Step 1.1: Baseline the state of the art

```text
/aar-start-research {topic}
```

It uses the `literature-discovery` skill. To run the search yourself:

```bash
python <skills>/literature-discovery/bin/sota_baseline.py --query "Your Topic" --output baseline.yaml
```

`sota_baseline.py` needs Semantic Scholar; if it answers `429`, use
`openalex_discovery.py` with the same flags, or set `S2_API_KEY`.

### Step 1.2: Set up the benchmark and data

Before the DAG, fix the testing environment every node will be measured in:

1. Dataset: put the research data in `performance/data/{project_name}/`.
2. Benchmark: put the evaluation code in `performance/benchmarks/evaluate_{metric}.py`.
   The audit's clean-room check compares this folder with `main`.
3. Baseline: run the benchmark against the current code and confirm it reproduces the
   figure you will record on H-000.

### Step 1.3: Create the DAG

`/aar-start-research` writes `research/hypothesis-dag.yaml` with:

- `metadata.primary_metric`: the metric every node is measured by.
- H-000: the baseline, external state of the art or your current system, with its
  measured performance.
- The first avenues as `pending` nodes under it.

It also asks AAW for the initiative and the root work item. To write the file by hand,
start from the [quick start's example](quick-start.md#4-write-a-tiny-dag).

---

## 2. Proposing and framing avenues

### Step 2.1: Add hypotheses

```text
/aar-update-lineage
```

or directly:

```bash
python <skills>/research-dag/bin/dag_update.py --action add --parent H-001 --hypothesis "New variant description" --target 0.05 --metric accuracy
python <skills>/research-dag/bin/generate_node_index.py
```

`dag_update.py` edits the DAG at `dag_path` from `research.yaml`; pass `--dag` to name
another file. Regenerate the index after every change, or the new node stays invisible to
the skills that read `ready`.

When more than one machine or agent works on the DAG, keep it in a shared DAG store: set
`dag_store` and `dag_project` in `research.yaml` and seed the project once with
`dag_store.py import`. The same `dag_update.py` commands then write events to the store
and regenerate `hypothesis-dag.yaml` as a view. Use the id the command reports for a new
node, which carries a letter suffix if a concurrent writer took the id first. See
[the shared DAG store](../skills/research-dag/references/dag-store.md).

### Step 2.2: Frame a hypothesis (design phase)

```text
/aar-start-hypothesis {node_id}
```

- Checks the node is `ready` in the node index, and warns if it is `blocked`.
- Delegates to AAW `/aaw-start-work` to create a research work item with `scope.md`,
  `research.md` and `plan.md`.
- Records the work item on the node and moves it from `pending` to `framed`.

Framing is worth doing even if the experiment waits: the design is captured while the idea
is fresh.

---

## 3. Executing research (execution phase)

### Step 3.1: Progress the hypothesis

```text
/aar-progress-hypothesis {WI_id} {node_id}
```

- First call: creates the branch `research/{node_id}-{topic}`, writes the work item's
  `metadata.yaml` with the parent's performance and the target, and moves the node to
  `in_progress`. The helper behind this is
  `python <skills>/research-dag/bin/branch_manager.py --action init --node-id H-001 --topic "day of week" --agent-id me --parent-perf 0.81 --target-imp 0.03 --target-dir <work item folder>`.
- Then: delegates to AAW `/aaw-progress-work` to execute the tasks, recording a finding
  and what prompted it for each activity.

`/aar-progress-research` does steps 2.2 and 3.1 for the next ready node without you naming
it.

### Step 3.2: Write it up

When the work is done, write the outputs in the work item's `deliverables/` from the
templates in `<skills>/aar-progress-hypothesis/assets/templates/`:

- `blog_template.md` to `deliverables/{node_id}-blog.md`
- `arxiv_template.md` to `deliverables/{node_id}-arxiv.md`
- `pivot_template.md` to `deliverables/{node_id}-pivot.md`, when the result missed its
  target

---

## 4. Verification and synchronisation

### Step 4.1: Audit

```text
/aar-run-audit
```

The Auditor re-runs the benchmark in a clean room. From the work item folder that holds
`metadata.yaml`:

```bash
python <skills>/aar-run-audit/scripts/audit_verify.py --action verify --clean-room
```

It checks the result improved on the parent (it treats lower as better), that the
deliverables exist, and that `performance/benchmarks/` matches `main`.

Check whether the research is live, as opposed to merely true:

```bash
python <skills>/aar-reconcile/scripts/reconcile.py --dag research/hypothesis-dag.yaml --cwd .
```

### Step 4.2: Synchronise the result

Once the AAW work item is `done`:

```text
/aar-sync-research-result {node_id} {WI_id}
```

It sets the node to `validated` or `ineffective` against the target fixed in step 3.1 (or
`discarded` if the work stopped), links the deliverables, regenerates the index so
unblocked children become `ready`, and proposes the hand-back to AAW.

### Step 4.3: Merge

Merge the research branch into `main`, with the updated `hypothesis-dag.yaml`.

---

## 5. Keeping the record true

| When | Run |
|---|---|
| After a batch of changes | `/aar-housekeep`: index, reference check, dashboard |
| Regularly, or before a merge | `/aar-reconcile`: adoption drift. `reconcile.py` exits 1 on drift |
| A new avenue appears | `/aar-update-lineage` |

---

## Summary of tools

| Tool | Role | Purpose |
|---|---|---|
| `sota_baseline.py`, `openalex_discovery.py`, `s2_ranking.py` | Specialist | Literature search and the state-of-the-art baseline |
| `dag_update.py` | Specialist | Adding and updating nodes, with locking, or through the DAG store |
| `generate_node_index.py` | All | Which nodes are ready |
| `branch_manager.py` | Worker | Research branches and `metadata.yaml` (used by `/aar-progress-hypothesis`) |
| `audit_verify.py` | Auditor | Verification with the clean-room check |
| `reconcile.py` | Reconciler | The DAG against the running system; reports drift, proposes nothing |
| `validate_dag_references.py`, `generate_dashboard.py` | Housekeeper | Orphaned ids and the dashboard |
| `dag_store.py` | All | The shared DAG store |
| `/aar-sync-research-result` | Worker | The return path from AAW to the DAG |

Every flag is in the [command reference](commands.md).
