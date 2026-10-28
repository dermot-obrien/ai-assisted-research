# Protocol

The procedure every agent follows to keep and replay experiments, so that any two agents, in any tool, leave the same record. MUST and MUST NOT are requirements; SHOULD is the default, to be departed from only with the reason written in `--note`. `<vault.py>` is `python <skills>/experiment-vault/bin/vault.py`. What each step relies on is in [guarantees](guarantees.md).

## 1. When a capsule is required

1.1. A run MUST be captured when any number it produces will be reported to a person, recorded on a node (`actual_performance`, `evidence`, notes), compared with a target, or used to decide what to try next. Exploratory and debugging runs need not be, except on a registered dataset, where they run through `vault.py run --exploratory` (6.5.2).

1.2. A reported number MUST come from one capsule. A result over several seeds or folds SHOULD be one command that runs them all and writes one metrics file with the aggregate and each seed; otherwise each seed is its own capsule and the report names every capsule.

1.3. A run that already happened outside the vault MAY be kept with `capture`, with `--note` saying so. If it can still be run, run it again through `run` instead: a `capture` records the command, it does not prove the outputs came from it.

## 2. Before the run

2.1. Full clone. `git rev-parse --is-shallow-repository` MUST print `false` in every repository the run uses; if not, run `git fetch --unshallow`. A shallow clone is kept as a whole snapshot, which works but stores the tree again for every commit.

2.2. Submodules. Every submodule MUST be checked out: `git submodule update --init --recursive`.

2.3. Commit. Every change that affects the run MUST be committed, in every repository the run uses, and the branch SHOULD be pushed. `--allow-dirty` SHOULD NOT be used for a result that will be recorded.

2.4. Inputs. Every file the run reads MUST be inside the main repository, in a folder named with `--data` (git-ignored when large; a symlink to data elsewhere is followed), or be a registered dataset named with `--dataset` ([datasets](datasets.md)). Data the run would fetch from the network MUST be fetched first, by a separate step. Data that more than one test reads, or that grows, SHOULD be registered (`dataset create`, `dataset add`) and read with `--dataset`, so it is stored once and every result names its version.

2.4a. Windows. A test of a node whose framing fixed a window MUST run on that window (`--dataset <name>@<version>:<mount>:<window>`) and read only that part of the data, as `VAULT_DATASETS` describes it. A run that is not evidence (trying a loader, a quick look) MUST carry `--exploratory`. A sealed holdout is looked at once per node, and not by a sibling of a node that looked. Section 6 gives every step.

2.5. Outputs. The run MUST write into folders named with `--outputs`, and those folders SHOULD be emptied (or new) before the run. `run` keeps as outputs only the files written during the run, and warns about any it left out, so a file from an earlier run is never kept as this run's output; `capture` cannot tell, so for a capture the folders MUST hold only that run's outputs.

2.6. Metrics. The run MUST write one JSON file of metrics (`--metrics`), with the node's metric under the key named by `--metric` (dotted for nested keys).

2.7. Seeds. Set `PYTHONHASHSEED`. Pass every seed both to the command and as `--seed name=value`.

2.8. Tolerance. Pass the `--rtol` and `--atol` the framing fixed. Without them the workspace defaults apply (1e-9 and 1e-12), which suit deterministic CPU work only.

2.9. Preflight. Run the exact command you will run, with `--dry-run` added. It MUST end `ready: nothing was run, tagged or uploaded`. Fix every `PROBLEM` line; never work around one with a flag. Read the plan lines: each repository, its storage (`bundle`) and how many commits are new to the vault.

## 3. The run

3.1. Run the same command without `--dry-run`, with all of: `--node`, `--data`, `--outputs`, `--metrics`, `--metric`, `--seed`, `--note` (why this run), `--agent` (your handle), `--work-item`, and `--rtol` and `--atol` where fixed. Extra repositories the code imports by path go in `--repo`.

```bash
export PYTHONHASHSEED=0
<vault.py> run --node H-204.4.16 --data data/prices --outputs out --metrics out/metrics.json --metric accuracy \
  --seed numpy=7 --rtol 1e-6 --atol 1e-9 --note "first run of the framed design" --agent my-agent --work-item WI-042 \
  -- python evaluate.py --seed 7
```

3.2. Let it finish. A run that fails is still kept, with its exit code and output; report it as a failed run, never as a result.

## 4. After the run

4.1. The output MUST show `Capsule <node>/<id>` and `Recorded on <node>: capsules += <id>`. If the second line is missing, record the capsule on the node yourself with the entry the tool printed: `dag_update.py --action append --node-id <node> --field capsules --value '<entry>'`.

4.2. Verify against the node: `<vault.py> verify <node>/<id> --sha256 <sha256 from the node's capsules entry>`. It MUST print `ok`.

4.3. Report in this form, and cite the capsule id wherever the number appears afterwards:

```
<node>: <metric> = <value> against a target of <target>, <evidence class> evidence. Capsule <node>/<id>; code <repo>@<commit12> (tag vault/<commit12>); data <dataset> <version> (<window>) or <n> data files; replay tolerance rtol <r>, atol <a>.
```

4.4. A tool warning (a tag that did not push, a commit on no remote branch, an unpinnable package) MUST be passed on to the person in the same report.

## 5. Replaying and retesting

5.1. To reproduce a result: `<vault.py> replay <node>/<id>`. To ask whether it still holds after a change, use the form for the change: `--pip <package>==<version>`, `--setup none`, or a new `run ... --retest-of <node>/<id>` for new code or data ([replaying](replaying.md)). Read the command, paths and seeds from `<vault.py> show <node>/<id>`, never from memory.

5.2. Report the verdict as the tool prints it, with every metric that moved. A `drifted` verdict MUST NOT be retried until it passes; it is a finding. A `failed` replay says nothing about the result: fix why it could not run (a missing system library, a moved path) and replay again.

5.3. Every replay is kept as a retest capsule (the default). `--no-record` is for a dry check only, and its verdict MUST NOT be reported as a retest.

## 6. Datasets, windows and evidence

The steps for data that several tests read or that grows, and for any test whose evidence depends on what data it could have seen, such as a backtest. [Datasets](datasets.md) explains the ideas; this section is what to do. Each step names who does it: you (the agent) or the person.

### 6.1 Who does what

| Action | Who |
|---|---|
| `dataset create`, `dataset add` that only adds (new files, or files extended at their end) | You |
| `dataset add --revise` on a `revisable` dataset | You, with the reason in `--revise` |
| `dataset add --revise --allow-append-only-revision` | The person, at a terminal. Never you |
| `dataset window` for `backtest` and `forward` windows | You, at framing, as written in the plan |
| `dataset window` for a `holdout` window | You, at framing, only for a span the person approved in the plan, quoted in `--note` |
| `run --override-holdout` | The person, at a terminal. Never you |
| Answering any prompt that asks you to type a dataset's name | The person. Never you, and never by piping input |

### 6.2 Registering data

6.2.1. Data that a second test will read, that will grow, or that a backtest, holdout or forward test uses MUST be registered; data read by one test only MAY stay under `--data`.

6.2.2. Before registering, check it is not already there: `<vault.py> dataset list`. Choose the rule from what the data are, not from convenience: data that only accumulate are `append-only`, data that are corrected or re-derived are `revisable`, a published benchmark or fixed split is `frozen`.

6.2.3. Register it with every source you know (`--source`, repeatable), its `--licence` and `--owner`, then add the first version from a folder holding the whole dataset:

```bash
<vault.py> dataset create <name> --rule append-only --title "<what it is>" --source "<url or vendor>" --licence "<terms>" --owner <who>
<vault.py> dataset add <name> --from <folder> --source "<where and when this pull came from>" --fetched-by "<script>@<commit12>" --note "<why>" --agent <handle>
```

6.2.4. The folder MUST be the whole dataset as it now stands, not only the new rows: the vault works out what was added. Fetching runs as its own step before `dataset add`, and the fetch script SHOULD be committed, so `--fetched-by` names a commit. Pass `--source-checksums <file>` when the source publishes checksums.

### 6.3 New data arriving

6.3.1. Fetch into the same folder, then `dataset add <name> --from <folder> ...` as in 6.2.3. It prints `Added <name> vNNNN: ...` or `No change ...`; report the version.

6.3.2. If it refuses with `is append-only` or `is frozen`, the source changed data it had already given. Do not edit the folder to make it pass, do not register it under another name, and do not use `--revise`. Stop, and tell the person which files changed (`dataset show <name> --files` against the folder) so they decide.

### 6.4 Framing a test on a dataset

6.4.1. The plan MUST fix, before any run of the node on the dataset: the dataset and version (`latest` is allowed for forward tests only), the windows by name and span, the evidence class of each run, and the decision rule (the target on the backtest, the target on the holdout, the forward checkpoints and the rule that retires the node).

6.4.2. Define the windows the plan names (6.1) that do not exist yet, and check them: `<vault.py> dataset show <name>`. A holdout that overlaps a backtest window is refused; do not shift it to fit without the person.

6.4.3. A node can share its parent's windows. Siblings share one holdout look between them (6.6), so frame which sibling is the one judged on the holdout, or give siblings their own holdout windows, approved by the person.

### 6.5 Running

6.5.1. Every run on a registered dataset goes through `vault.py run --dataset <name>@<version>:<mount>:<window>`. The mount is a folder inside the repository that git ignores (add it to `.gitignore` and commit that first). The run MUST read the dataset from the `path` in the file `VAULT_DATASETS` names, and only the part of it its `window` names:

| Window class | The run reads |
|---|---|
| `backtest`, `holdout` | Only rows whose date is from `from_date` to `to_date` inclusive, in the data's own date format |
| `forward` | Only the bytes of each file from its `forward_offsets` entry on (0 for a file that is new) |

6.5.2. Runs while developing (a new loader, a parameter search, debugging) MUST use the backtest window with `--exploratory`. They are kept, and never count as evidence.

6.5.3. The test itself is the same command, with the same `--dataset`, without `--exploratory`, after `--dry-run` printed `ready`. Its evidence class is printed as `evidence: <class>`; it MUST be the class the plan fixed.

6.5.4. Run on the holdout once, when the design is final and its backtest met the plan's target: the dry run must print `ready`, the command must be committed, and nothing may change between the dry run and the run. The look is spent when the run starts, even if it fails.

6.5.5. A forward test is the node's committed command run on `<name>@latest:<mount>:<forward window>` after each new version (6.3), unchanged between runs. Record each run on the node as it comes; compare it with the checkpoints only where the plan placed them.

6.5.6. A run on a dataset MUST NOT read it any other way: not through `dataset fetch`, not from the cache folder, not from the source folder. `dataset fetch` is for a person inspecting data.

### 6.6 Holdout refusals

| The tool says | Do |
|---|---|
| `already looked at by <node> (this node)` | The node's one look is spent. Report the recorded holdout capsule (`dataset uses <name> --window <window>`) as the result. Do not run again |
| `already looked at by <node> (a sibling of this node)` | The look belongs to the sibling. Report it to the person; they decide whether this node gets a holdout of its own |
| `is not in the DAG` | Add the node with `dag_update.py`, refresh the view, then run again |
| `has a sealed holdout, so a run on it names its window` | Add the window the plan fixed to `--dataset` |

Never get round a refusal by renaming or re-parenting a node, defining a new window, registering the data again, or reading the data outside the vault.

### 6.7 Reporting and status

6.7.1. Report a dataset result as 4.3 gives it, with `<evidence class> evidence` and `data <dataset> <version> (<window>)`.

6.7.2. The status a result can give the node follows from its evidence class and the plan, and the research flow sets it (`/research sync`, by the research-dag skill's `references/node-schema.md`):

| Class | Met the target | Missed it |
|---|---|---|
| `exploratory` | No change: the node stays `in_progress` | No change |
| `untracked` | `validated` if the plan fixed no window; otherwise no change | `ineffective` |
| `backtest` | `backtested`, or `validated` if the plan fixed no holdout or forward window | `ineffective` |
| `holdout` | `holdout_passed`, or `validated` if the plan fixed no forward window | `ineffective` |
| `forward`, at a checkpoint | `forward_testing`, or `validated` at the checkpoint the decision rule names | `contested`, or `retired` by the retire rule |

6.7.3. After a revision (the person's, or yours on a `revisable` dataset), run `<vault.py> dataset impact <name>@<new version>` and pass every listed capsule to `/research retest`, except holdout results, which go to the person (6.6).

## 7. Runtimes: the same result on any machine

The steps for a node whose result must not depend on where it ran or which agent platform ran it. [Runtimes](runtimes.md) explains the ideas.

7.1. A node that will be tested more than once, on more than one machine, or by more than one agent platform SHOULD fix a runtime at framing; a node in a pool (the research skill's `references/pool.md`) MUST. Use one the project already has (`<vault.py> runtime show`) unless the plan needs other packages, a newer Python or other settings; then define a new one ([runtimes](runtimes.md), Making one) and set it on the node: `dag_update.py --action set --node-id <node> --field runtime --value <name>`. Never change a runtime; define a new one.

7.2. Before running on a machine for the first time, check it: `uv python install <the runtime's Python>`, `uv sync --frozen --python <version> --managed-python`, then `<vault.py> runtime check <name> --python .venv/bin/python`. It MUST print `matches runtime <name>`. On a Windows PC, do all of this in WSL2.

7.3. Run with the project's environment: `--python .venv/bin/python`, and the same interpreter in the command after `--`. The vault sets the profile's variables itself; do not set them by hand, and do not pass `--rtol` or `--atol`, which the runtime fixes. Pass `--tool <your platform>` (`claude-code`, `cursor`, `codex`, `copilot`, `jules`, `devin`, `openhands`) unless `VAULT_AGENT_TOOL` is set.

7.4. Write the experiment by the rules in [runtimes](runtimes.md) (Writing experiments that give the same numbers anywhere): money in integers, sums in a fixed order, float64, no parallel reductions, every seed passed, metrics rounded at the precision the plan fixed.

7.5. A run refused with `cannot be evidence` did not run. Fix what it lists; never get round it with `--exploratory` for a number that will be reported, by another runtime, or by removing the node's runtime.

7.6. Parity. When the runtime requires it, a result counts only once another machine or platform has replayed its capsule identically: `<vault.py> replay <node>/<capsule> --tool <platform>` in a different session or tool, then `<vault.py> parity <node>/<capsule>` MUST exit 0 before the node's status moves. A parity replay that is not `identical` is a finding: report it, and the node becomes `contested`.

7.7. Report a runtime result as 4.3 gives it, with `runtime <name>, parity <yes or pending>`.

## 8. When something goes wrong

| The tool says | Do |
|---|---|
| `has uncommitted changes` | Commit (2.3) and run again |
| `is a shallow clone` | `git fetch --unshallow` (2.1); the capsule already kept is valid, as a snapshot |
| `submodule ... is not checked out` | `git submodule update --init --recursive` (2.2) |
| `is outside ...` | Move or symlink the path inside the repository (2.4) |
| `looks like a secret` | Remove `--env` for it; pass secrets another way. Secrets never go in a capsule |
| `could not push tag` | Report it (4.4). The capsule is complete; push the tag later with `git push origin refs/tags/vault/<commit12>` |
| `no research.yaml with the research-dag skill beside this one` | Record the capsule by hand (4.1) |
| `is corrupt`, `missing from`, `bundles missing`, `not the recorded` | Stop. Report the capsule and the message to the person. Never repair, rewrite or delete anything in the vault |
| `cannot read; update the skill` | Update experiment-vault; never edit the manifest |
| `RESEARCH_VAULT_GCP_KEY is not JSON`, `neither JSON nor base64 JSON`, `is not a service account key` | The environment's key variable is wrong. Tell the person; never print, echo or edit the variable |
| `is append-only`, `is frozen`, `needs a person` | The data changed in a way its rule forbids. Register the new data as a new version only if it only adds; otherwise tell the person, who decides on a revision |
| `already looked at by` | See 6.6 |
| `has a sealed holdout, so a run on it names its window`, `overlaps` | Name the window the plan fixed (6.5.1); windows that overlap are refused, so take it to the person |
| `is not in the DAG` | Add the node, or refresh the view, and run again |
| `the run changed dataset` | The experiment wrote into its input. Fix it to write under `--outputs` and run again |
| `cannot be evidence`, `is not the project's environment`, `does not match uv.lock` | The run does not match the node's runtime (7.5). `uv sync --frozen` and run with `.venv/bin/python`; on another machine type, run where the runtime's machine type is |
| `lacks`, `which profile` | This CPU cannot run the profile's code path; run on another machine |
| `there is no runtime` | The node names a runtime the vault does not hold; define it (7.1) or fix the node |
| `a capture cannot show the machine a past run ran on` | Run it again through `vault.py run` (7.5) |
| `has no identical replay on another machine in its runtime yet` | Replay it in another session or platform (7.6) before the status moves |
| `not initialised, or not reachable` | Check `vault.uri` and the gcloud sign-in; a person creates the bucket ([storage](storage.md)) |

## 9. Never

- Never edit, overwrite, move or delete anything in the vault, or a `vault/*` tag.
- Never record a number as a result without the capsule it came from.
- Never report a retest that was run with `--no-record`, or a `drifted` replay re-run until it passed.
- Never pass a secret with `--env`, or put one in the command line or the console output. Never print, copy or write out `RESEARCH_VAULT_GCP_KEY`; the tool reads it.
- Never hand-write a manifest or a `capsules` entry: copy the one the tool printed.
- Never revise an append-only dataset, override a holdout, or answer a prompt that asks for a person (6.1).
- Never read a registered dataset except through `vault.py run --dataset`, or outside the window the run names (6.5).
- Never report a number from a run its node's runtime refused, or move a node whose runtime requires parity before `parity` passes (7).
