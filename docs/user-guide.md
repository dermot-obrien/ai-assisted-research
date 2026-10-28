# User guide

The full research cycle, step by step, for human researchers and the agents working with
them. It assumes the four research skills (`research`, `research-dag`, `experiment-vault` and
`literature-discovery`) and AAW's `work` skill are installed in the workspace; the
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
/research init
```

The Discovery role scans early commits, READMEs and docs for the kernel idea and the major
shifts since, citing a commit, pull request or file and line for each. Its helper gathers
the first markers:

```bash
python <skills>/research/scripts/discovery.py
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
/research start {topic}
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
4. Vault: set `vault.uri` (and `vault.project`, or `dag_project`) in `research.yaml`, so
   every measured run is kept as a capsule; see
   [configuration](configuration.md#the-experiment-vault). For a bucket, a person creates it
   once, as the experiment-vault skill's
   [storage reference](../skills/experiment-vault/references/storage.md) shows, then runs
   `python <skills>/experiment-vault/bin/vault.py init`. A folder works for a start. Keep
   the data inside the repository (git-ignored if large), since a capsule records data by
   its path there.

### Step 1.3: Create the DAG

`/research start` creates `research.yaml` from the research skill's `assets/research.yaml.example` when the workspace has none, and the research folder, then writes `research/hypothesis-dag.yaml` with:

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
/research lineage
```

or directly:

```bash
python <skills>/research-dag/bin/dag_update.py --action add --parent H-001 --hypothesis "New variant description" --plain-tested "What it tests, in plain words" --target 0.05 --metric accuracy
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
/research frame {node_id}
```

- Checks the node is `ready` in the node index, and warns if it is `blocked`.
- Delegates to AAW `/work start` to create a research work item with `scope.md`,
  `research.md` and `plan.md`.
- With a vault, writes into the plan what the run will capture: the command, the inputs
  and outputs by path, the seeds, the metric key and the tolerance a replay must meet
  (`--rtol`, `--atol`). Fixing them now, like the target, is what lets a later agent replay
  the experiment.
- Records the work item on the node and moves it from `pending` to `framed`.

Framing is worth doing even if the experiment waits: the design is captured while the idea
is fresh.

---

## 3. Executing research (execution phase)

### Step 3.1: Progress the hypothesis

```text
/research run {WI_id} {node_id}
```

- First call: creates the branch `research/{node_id}-{topic}`, writes the work item's
  `metadata.yaml` with the parent's performance and the target, and moves the node to
  `in_progress`. The helper behind this is
  `python <skills>/research-dag/bin/branch_manager.py --action init --node-id H-001 --topic "day of week" --agent-id me --parent-perf 0.81 --target-imp 0.03 --target-dir <work item folder>`.
- Then: delegates to AAW `/work progress` to execute the tasks, recording a finding
  and what prompted it for each activity.

`/research progress` does steps 2.2 and 3.1 for the next ready node without you naming
it.

### Step 3.2: Capture every measured run

With a vault configured, every run whose numbers you will report goes through the
experiment vault, after committing:

```bash
python <skills>/experiment-vault/bin/vault.py run --node H-001 --data performance/data/demo --outputs out/ --metrics out/metrics.json --metric accuracy --seed numpy=7 --work-item WI-042 -- python performance/benchmarks/evaluate_accuracy.py --seed 7
```

It keeps the code at its commit, the data, the environment, the command, its console output
and the outputs as a capsule, and appends the capsule to the node's `capsules`. Set
`PYTHONHASHSEED` first for a bit-identical replay. Exploratory runs need not be captured,
but a number that did not come from a capsule cannot be replayed, so it is not the result.
For a run that already happened, `vault.py capture --cmd "..."` keeps its outputs; say so in
`--note`.

### Step 3.3: Write it up

When the work is done, write the outputs in the work item's `deliverables/` from the
templates in `<skills>/research/assets/templates/`:

- `blog_template.md` to `deliverables/{node_id}-blog.md`
- `arxiv_template.md` to `deliverables/{node_id}-arxiv.md`
- `pivot_template.md` to `deliverables/{node_id}-pivot.md`, when the result missed its
  target

---

## 4. Verification and synchronisation

### Step 4.1: Audit

```text
/research audit
```

The Auditor first replays the node's capsule, where it has one:

```bash
python <skills>/experiment-vault/bin/vault.py replay H-001/<capsule id>
```

It restores the exact code, data and environment into a new folder, runs the recorded
command and reports `identical`, `reproduced`, `drifted` or `failed` (exit 0, 0, 3 or 1),
kept as a retest capsule on the node. That proves the result can be made again from what was
recorded, not that the evaluation was sound, so the Auditor then re-runs the benchmark in a
clean room. From the work item folder that holds `metadata.yaml`:

```bash
python <skills>/research/scripts/audit_verify.py --action verify --clean-room
```

It checks the result improved on the parent (it treats lower as better), that the
deliverables exist, and that `performance/benchmarks/` matches `main`.

Check whether the research is live, as opposed to merely true:

```bash
python <skills>/research/scripts/reconcile.py --dag research/hypothesis-dag.yaml --cwd .
```

### Step 4.2: Synchronise the result

Once the AAW work item is `done`:

```text
/research sync {node_id} {WI_id}
```

With a vault configured, it first checks the node names the capsule the metric came from,
with that metric as its `result.value`, and that it is intact:

```bash
python <skills>/experiment-vault/bin/vault.py verify H-001/<capsule id> --sha256 <sha256 from the node>
```

With no capsule, it captures the run now if it can still be run, or from its outputs with
`vault.py capture`; a result with neither stays `in_progress`. Then it sets the node to
`validated` or `ineffective` against the target fixed in step 3.1 (or
`discarded` if the work stopped), links the deliverables, regenerates the index so
unblocked children become `ready`, and proposes the hand-back to AAW.

### Step 4.3: Merge

Merge the research branch into `main`, with the updated `hypothesis-dag.yaml`.

---

## 5. Keeping the record true

| When | Run |
|---|---|
| After a batch of changes | `/research housekeep`: index, capsule coverage (`vault.py coverage --verify`), reference check, dashboard |
| A library, the environment, the code or the data a result rests on changes | `/research retest {node_id} [what changed]`; see below |
| Regularly, or before a merge | `/research reconcile`: adoption drift. `reconcile.py` exits 1 on drift |
| A new avenue appears | `/research lineage` |

### Retesting a result

```text
/research retest H-001 "numpy 2.1"
```

The flow takes the node's newest `run` capsule, verifies it, and replays it with the change:

| What changed | It runs |
|---|---|
| Nothing, or "does it still reproduce" | `vault.py replay <capsule>` |
| A library | `vault.py replay <capsule> --pip numpy==2.1.0` |
| The environment as a whole | `vault.py replay <capsule> --setup none`, in the new environment |
| The code or the data | After a commit, `vault.py run --node H-001 --retest-of <capsule> ... -- <the same command>` |

`identical` and `reproduced` add a note and leave the status. `drifted` adds a note with each
metric that moved and, for a `validated` or `ineffective` node, sets it to `contested`, for
you to decide: a new child hypothesis that explains the change, or an audit. `failed` adds a
note only. `--all-validated "<what changed>"` retests every validated node the change
touches.

---

## Summary of tools

| Tool | Role | Purpose |
|---|---|---|
| `sota_baseline.py`, `openalex_discovery.py`, `s2_ranking.py` | Specialist | Literature search and the state-of-the-art baseline |
| `dag_update.py` | Specialist | Adding and updating nodes, with locking, or through the DAG store |
| `generate_node_index.py` | All | Which nodes are ready |
| `branch_manager.py` | Worker | Research branches and `metadata.yaml` (used by `/research run`) |
| `audit_verify.py` | Auditor | Verification with the clean-room check |
| `vault.py` | Worker, Auditor, Housekeeper | Capturing runs as capsules, replaying and retesting them, checking coverage |
| `reconcile.py` | Reconciler | The DAG against the running system; reports drift, proposes nothing |
| `validate_dag_references.py`, `generate_dashboard.py` | Housekeeper | Orphaned ids and the dashboard |
| `dag_store.py` | All | The shared DAG store |
| `/research sync` | Worker | The return path from AAW to the DAG |

Every flag is in the [command reference](commands.md).
