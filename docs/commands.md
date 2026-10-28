<!--
SPDX-FileCopyrightText: 2026 Dermot O'Brien
SPDX-License-Identifier: CC-BY-4.0
-->

# Command reference

Every command AAR ships, with every flag, checked against each tool's `--help`. Run the
Python tools from the workspace (they find `research.yaml` by searching upward), with the
path to wherever the skills are installed, usually `.agents/skills/`. Below, `<skills>`
stands for that folder.

Exit codes are 0 for success and 1 for an error unless a tool says otherwise. Argument
errors from Python's argparse exit 2.

## Skills, in an agent

The workflows are Agent Skills. Type `/` and the skill name where your agent supports
slash invocation, or ask in plain words and let the agent pick the skill by its
description. [Skills](skills.md) describes each.

| Invocation | Arguments |
|---|---|
| `/research start {topic}` | The problem to research |
| `/research init` | None; works on the current repository |
| `/research lineage` | What to add or change, in words |
| `/research progress` | None, or a node id |
| `/research frame {node_id}` | e.g. `H-001` |
| `/research run {WI_id} {node_id}` | e.g. `WI-042 H-001` |
| `/research sync {node_id} {WI_id}` | e.g. `H-001 WI-042` |
| `/research audit` | None, or a node id |
| `/research retest {node_id} [what changed]` | e.g. `H-001 "numpy 2.1"`; or `--all-validated "<what changed>"` |
| `/research reconcile` | None |
| `/research pool` | None: offer what may start, or take a hypothesis as a worker |
| `/research campaign {id}` | e.g. `RT1`: retest every result from the root down |
| `/research housekeep` | None |
| `/research dag` | Points to the research-dag skill's tools |
| `/literature-discovery` | Searches the literature; `/research start` uses it for the baseline |

## Installing (skills.mjs)

AAR ships no installer. The skills install with AI-Assisted Work's `bin/skills.mjs`; its own help (`node <aaw>/bin/skills.mjs help`) and AAW's [command reference](https://github.com/dermot-obrien/ai-assisted-work/blob/main/docs/reference/commands.md) list every flag. The commands AAR's documentation uses:

| Command | Effect |
|---|---|
| `skills.mjs install --bundle <clone of this repository>` | Copy the four skills to `.agents/skills/<name>/`, link `.claude/skills/<name>` when `.claude/` exists, and record them in `.agents/skills.lock.json` |
| `skills.mjs install research --bundle <clone>` | The same, for the one skill named |
| `skills.mjs install work` | Install the `work` skill that `research` requires, from the bundle beside the script |
| `skills.mjs sync [--locked] [--copy]` | Install what `.agents/skills.json` declares and remove what this installer put there that it no longer declares; `--locked` installs the commits in the lock |
| `skills.mjs check` | A tick or a cross per installed skill; exit 1 when one changed or is missing |

It installs no Python packages and creates no `research.yaml`: run `python -m pip install -r requirements.txt` from a clone, and let `/research start` or `/research init` create `research.yaml` from `skills/research/assets/research.yaml.example` (or copy it yourself).

## research-dag tools

In `<skills>/research-dag/bin/`. All need PyYAML and read `research.yaml`.

Until research 4.0.0 these tools were in `<skills>/research/bin/`. Launchers at those paths
still run research-dag's copy, with the same arguments, until research 5.0.0. Each prints
`note: research/bin/dag_update.py moved to research-dag/bin/dag_update.py; this path goes in research 5.0.0.`
to stderr first (with its own name), or, when research-dag is not installed beside research,
says so and exits 2. Use the new paths.

### dag_update.py

Change the DAG. The only supported way to edit it.

```text
python <skills>/research-dag/bin/dag_update.py --action ACTION [options]
```

| Flag | Used by | Meaning |
|---|---|---|
| `--action {add,update,adopt,relink,set,append,note}` | all, required | What to do |
| `--dag PATH` | all | The DAG file. Default: `dag_path` from `research.yaml`, else `hypothesis-dag.yaml`; with a DAG store, the view path |
| `--no-store` | all | Edit the YAML file directly even when a DAG store is configured |
| `--parent ID` | `add`, `relink` | The parent of a new node, or the new parent |
| `--hypothesis TEXT` | `add` | The hypothesis |
| `--target NUMBER` | `add` | Target improvement, default 0.0 |
| `--metric NAME` | `add` | Metric; warns if it differs from `metadata.primary_metric` |
| `--node-id ID` | `update`, `adopt`, `relink`, `set`, `append`, `note` | The node to change |
| `--status STATUS` | `update` | `pending`, `framed`, `in_progress`, `backtested`, `holdout_passed`, `forward_testing`, `validated`, `contested`, `ineffective`, `retired`, `discarded` |
| `--performance NUMBER` | `update` | Sets `actual_performance` |
| `--adoption STATE` | `adopt` | `not_assessed`, `not_applicable`, `not_adopted`, `partial`, `adopted`, `contradicted` |
| `--artefact TEXT` | `adopt` | Where the finding lives in the running system |
| `--verification CMD` | `adopt` | Shell predicate that exits 0 while the claim holds |
| `--adoption-note TEXT` | `adopt` | Why the node is at this state |
| `--field NAME` | `set`, `append` | Any field but `id` and `parent`; for `append`, a list field |
| `--value YAML` | `set`, `append` | Parsed as YAML: `0.07`, `[a, b]`, `null`; for `append`, the one item to add |
| `--note TEXT` | `note` | Appended to `notes` |

Required per action: `add` needs `--parent` and `--hypothesis`; `update` needs `--node-id`
and `--status`; `adopt` needs `--node-id` and `--adoption`; `relink` needs `--node-id` and
`--parent`; `set` and `append` need `--node-id`, `--field` and `--value`; `note` needs
`--node-id` and `--note`.

`append` adds one item to a list field, starting the list when the field is unset. An item
already in the list is not added again, and a field that holds something other than a list
is refused (`Error: H-001 capsules is not a list; use --action set.`). In a DAG store it is
written as an append event, so items appended by concurrent writers all survive. Use it, or
`note`, for list fields such as `capsules`, `notes` and `avenues`, rather than setting the
whole list. The experiment vault records each capsule this way.

It prints `Added new node: H-001`, `Updated node: H-001`, `Set adoption of H-001 to
'adopted'`, `Moved H-002 under H-003`, `Set evidence of H-001`, `Appended to capsules of
H-001` or `Noted on H-001`; in a DAG store, a change that changes nothing ends `(no change)`.
The plain file is locked with `<dag>.lock` while it is written.

```bash
python <skills>/research-dag/bin/dag_update.py --action update --node-id H-001 --status validated --performance 0.845
python <skills>/research-dag/bin/dag_update.py --action set --node-id H-001 --field evidence --value "notebooks/eval.ipynb"
python <skills>/research-dag/bin/dag_update.py --action append --node-id H-001 --field capsules --value "{id: 20261021T101500Z-9aa09684e0db, kind: run}"
```

### generate_node_index.py

No options. Writes `node_index_path` and prints the count per list. `--help` prints its
description.

### generate_dashboard.py

No options. Writes `dashboard.output_html` and prints the node, experiment and ready counts
and a `file:///` link. `--help` prints its description.

### validate_dag_references.py

```text
python <skills>/research-dag/bin/validate_dag_references.py [--fix]
```

Scans `docs/`, `python/`, `ml_pipeline/` and `.irregular-timeseries-intent/` under the
workspace root, in `.py`, `.md`, `.yaml`, `.yml`, `.json` and `.jsonl` files, for ids like
`H-001` or `H-204.4.7b`, and reports any not in the DAG. `--fix` also prints a node stub for
each. With a DAG store it lists aliases too. Exit 0 when every reference resolves, 1 when
any is orphaned.

### branch_manager.py

```text
python <skills>/research-dag/bin/branch_manager.py --action {init,handoff} [options]
```

| Flag | Default | Meaning |
|---|---|---|
| `--action init` | | Create or check out `research/{node}-{topic}`, write `metadata.yaml`, commit it |
| `--action handoff` | | Update `metadata.yaml` for the next role and commit it |
| `--node-id ID` | | Required for both |
| `--topic TEXT` | | Required for `init`; lower-cased, spaces become hyphens |
| `--agent-id ID` | | Required for `init` |
| `--role ROLE` | `worker` | The current agent's role |
| `--parent-perf NUMBER` | `0.0` | The parent's performance |
| `--target-imp NUMBER` | `0.0` | The target improvement |
| `--target-dir DIR` | `.` | Where `metadata.yaml` lives |
| `--next-role ROLE` | | `handoff`: the next role; `auditor` sets status `awaiting_review` |
| `--instructions TEXT` | | `handoff`: instructions for the next role |
| `--performance NUMBER` | | `handoff`: sets `actual_performance` |

### dag_store.py

The shared DAG store. See [the store reference](../skills/research-dag/references/dag-store.md).

```text
python <skills>/research-dag/bin/dag_store.py [--store STORE] [--project PROJECT] COMMAND [options]
```

`--store` and `--project` override `dag_store` and `dag_project`, and are needed where
there is no `research.yaml`.

| Command | Options | Effect |
|---|---|---|
| `init` | | Clone the store if needed and create the project folder |
| `import` | `--from FILE` (default `dag_path`) | Seed an empty project, one event per node; refuses unless replay reproduces the file |
| `view` | `--view FILE` (default `dag_path`) | Pull and regenerate the YAML view |
| `report` | `--json`, `--no-pull` | Concurrent edits, aliases and orphaned events |
| `record` | `--view FILE` (default `dag_path`) | Turn edits made directly to the view into events |
| `prune` | `--days N` (default 90), `--statuses a,b` (default `discarded,ineffective,validated`), `--dry-run` | Archive the events of closed nodes; replay still reads them |
| `verify` | `--against FILE` (required), `--no-pull` | Check replay reproduces a YAML file |
| `sync` | | Push anything left unpushed |

Errors print `Error: ...` to stderr and exit 1.

### check.py (every skill)

```text
python <skills>/<skill>/bin/check.py
```

The post-install check, the same file in every skill. Run it from the workspace root;
`SKILL_DIR` names the skill (default: the folder above the script). It takes no
arguments. It checks the Python packages the skill's tools import, and `research.yaml` for
every skill but `literature-discovery` and `experiment-vault`; for `experiment-vault` it
also checks `git` is on the path. Prints `warning:` lines for paths not created yet, one line per problem, and
`<skill>: ok` when there are none. Exit 0 correct, 1 problems, 2 usage or environment
error (Python older than 3.10, or an argument).

## experiment-vault tools

In `<skills>/experiment-vault/bin/`. `vault.py` needs Python 3.10 or newer, PyYAML and git,
and the gcloud CLI, signed in with write access to the bucket, for a `gs://` vault. It reads
`research.yaml` when there is one; without one, pass `--vault` and `--project`.

```text
python <skills>/experiment-vault/bin/vault.py [--vault VAULT] [--project PROJECT] COMMAND [options]
```

| Flag | Meaning |
|---|---|
| `--vault VAULT` | The vault: a folder, `file://`, or `gs://bucket/prefix`. Overrides `RESEARCH_VAULT` and `vault.uri` |
| `--project PROJECT` | The project's folder in the vault. Overrides `RESEARCH_VAULT_PROJECT`, `vault.project` and `dag_project` |

Both go before the command. A relative folder resolves against the folder holding
`research.yaml` when there is one. Where a command takes `<capsule>`, give a capsule id
(`<stamp>-<hash12>`, looked up in the project), `<node>/<id>`, or the manifest's URI.

| Command | Options | Effect |
|---|---|---|
| `init` | | Write `VAULT.md`, the format for a reader without the tool, at the vault root. Needs no project |
| `run` | the capture options below, then `-- COMMAND` | Run the command and keep everything it used and produced as a capsule |
| `capture` | the capture options, `--cmd CMD` (required), `--exit-code N` (default 0), `--stdout FILE`, `--stderr FILE` | Keep a run that already happened as a capsule. `--cmd` is the command as one string |
| `list` | `--node ID`, `--long` | List capsules, one per line; `--long` reads each manifest for its kind, exit code, result and verdict |
| `show` | `<capsule>`, `--node ID`, `--json` | Summarise one capsule: code, data, environment, run, outputs, result, retest; `--json` prints the manifest |
| `verify` | `[<capsule>]`, `--node ID`, `--all`, `--sha256 HASH`, `--deep` | Check the manifest hashes to its id and every blob is present. `--sha256` is the hash the DAG records, to check against; `--deep` downloads and re-hashes every blob. Name a capsule, or pass `--node` or `--all` |
| `restore` | `<capsule>`, `--node ID`, `--to DIR` (required) | Materialise a capsule into an empty folder: `repos/<name>/` with the data in place, `env/`, `original-outputs/`, `CAPSULE.json`, and `replay.sh` and `replay.ps1` to run it by hand |
| `replay` | `<capsule>` and the replay options below | Restore a capsule, run it again, compare, and keep the replay as a `retest` capsule |
| `coverage` | `--verify`, `--strict` | List the DAG's result nodes (`validated`, `ineffective`, `contested`, the evidence statuses `backtested`, `holdout_passed`, `forward_testing` and `retired`, and the older result statuses) that have no capsule. `--verify` also checks every capsule the DAG names is intact and has the hash the DAG records |
| `dataset create` | `NAME`, `--rule append-only\|revisable\|frozen` (required), `--title`, `--description`, `--source` (repeatable), `--licence`, `--owner`, `--agent` | Register a dataset, once |
| `dataset add` | `NAME`, `--from FOLDER` (required), `--note`, `--source`, `--fetched-by`, `--source-checksums FILE`, `--revise REASON`, `--allow-append-only-revision`, `--agent` | Add the folder as the next version, if it differs, within the dataset's rule. A revision of an append-only dataset needs a person at a terminal |
| `dataset window` | `NAME WINDOW`, `--class backtest\|holdout\|forward` (required), `--from-date`, `--to-date`, `--from-version`, `--note` | Define a window, once. A forward window needs `--from-version` and an append-only dataset |
| `dataset list`, `show`, `diff`, `fetch` | `show NAME[@VERSION] [--files]`, `diff A B`, `fetch NAME[@VERSION] [--to DIR]` | Read datasets, their versions and windows; fetch a version, hash-checked |
| `dataset uses` | `NAME`, `--window WINDOW` | The capsules that read a dataset, and a holdout's claims and overrides |
| `dataset impact` | `NAME@VERSION`, `--strict` | The capsules built on earlier versions; `--strict` exits 1 when there are any |
| `runtime create` | `NAME`, `--python PY` (required), `--profile cpu-deterministic-v1\|none`, `--rtol` (default 0), `--atol` (default 0), `--no-parity`, `--note` | Define a runtime from an interpreter, once: machine type, Python build, uv lock, settings, tolerance |
| `runtime show`, `runtime check` | `show [NAME]`; `check NAME [--python PY] [--cwd DIR]` | What a runtime holds; whether this machine and environment match it (exit 2 when not) |
| `parity` | `<capsule>`, `--node ID` | Exit 0 when the capsule was replayed identically on another machine or platform that matched its runtime |
| `lifecycle` | `--nearline DAYS` (default 30), `--coldline DAYS` (default 90), `--archive DAYS` (default 365) | Print Cloud Storage lifecycle rules, as JSON, that move old objects to colder classes |

The capture options, for `run` and `capture`:

| Flag | Meaning |
|---|---|
| `--node ID` | Required. The hypothesis node the capsule belongs to |
| `--cwd DIR` | Where the command runs (default: here); must be in a git repository |
| `--name NAME` | Name for the main repository (default: its folder name) |
| `--repo PATH` | Another git repository the run used. Repeatable |
| `--data PATH` | A file or folder the run reads, inside the repository. Repeatable |
| `--dataset NAME@VERSION:MOUNT[:WINDOW]` | A registered dataset the run reads, linked at the git-ignored folder `MOUNT`; `VERSION` may be `latest`. Repeatable. The run finds them in the file `VAULT_DATASETS` names |
| `--exploratory` | The run is not evidence: its capsule's evidence class is `exploratory` |
| `--override-holdout REASON` | Look again at a sealed holdout; a person confirms at a terminal |
| `--runtime NAME` | The runtime the run must match, when the node fixes none; refused when it names another than the node's |
| `--tool NAME` | The agent platform making the run (`claude-code`, `cursor`, `codex`, …); default `VAULT_AGENT_TOOL`, or detected |
| `--outputs PATH` | A file or folder the run writes. Repeatable |
| `--metrics FILE` | The JSON file of metrics the run writes |
| `--metric KEY` | The metric (a dotted key in `--metrics`) that is the node's result |
| `--target NUMBER` | The target (default: the node's target in the DAG) |
| `--seed NAME=VALUE` | A seed the run uses. Repeatable |
| `--env NAME` | An environment variable that affects the result. Repeatable. Names that look like keys, tokens or passwords are refused |
| `--python PATH` | The interpreter the experiment uses (default: the one running `vault.py`) |
| `--vendor-wheels` | Store the wheel of every pinned package too (or set `vault.vendor_wheels: true`) |
| `--allow-dirty` | Allow uncommitted changes, stored as a patch; the capsule is marked dirty |
| `--code-storage bundle\|archive` | `bundle` (default, or `vault.code_storage`): tag the commit and keep the repository as incremental git bundles; `archive`: a compressed snapshot of the commit. A shallow clone always gets `archive` |
| `--no-push-tag` | Create the `vault/<commit12>` tag locally without pushing it to `origin` |
| `--dry-run` | Check everything the capture needs (vault reachable, clean full clones, submodules checked out, paths inside the repository, no secret `--env`, pip available) and print the plan; run, tag and upload nothing. Exit 0 and `ready`, or 2 with a `PROBLEM` line for each problem |
| `--strict` | Fail when the environment cannot be fully captured, instead of warning |
| `--rtol NUMBER`, `--atol NUMBER` | The relative and absolute tolerance a replay's metrics must meet (default: `vault.rtol` and `vault.atol`, else 1e-9 and 1e-12) |
| `--retest-of <capsule>` | A capsule this run retests: the capsule is of kind `retest` and the result is compared with it |
| `--note TEXT` | Why this run was made |
| `--agent NAME` | Who ran it: an agent handle or a person |
| `--work-item ID` | The work item the run belongs to |
| `--no-link` | Do not record the capsule on the DAG node |

Besides the variables named with `--env`, a capsule records `PYTHONHASHSEED`,
`CUBLAS_WORKSPACE_CONFIG`, `OMP_NUM_THREADS`, `MKL_NUM_THREADS`, `OPENBLAS_NUM_THREADS`,
`CUDA_VISIBLE_DEVICES`, `TZ`, `LANG` and `LC_ALL` whenever they are set.

The replay options:

| Flag | Default | Meaning |
|---|---|---|
| `--node ID` | | The node, when `<capsule>` is a bare id |
| `--to DIR` | `.vault-replay/<capsule id>` | Where to restore; must be empty or new |
| `--setup {venv,none}` | `venv` | `venv`: a fresh virtual environment from the capsule's lock, from its vendored wheels with no package index when it has them; `none`: this interpreter as it is, to retest against what has changed |
| `--python PATH` | this one | The base interpreter; a version other than the recorded one is warned about |
| `--pip REQ` | | A requirement to install over the lock, for example `numpy==2.1.0`. Repeatable. Needs `--setup venv` |
| `--rtol NUMBER`, `--atol NUMBER` | the capsule's | Override the tolerance fixed at capture |
| `--note TEXT`, `--agent NAME`, `--work-item ID` | | Recorded on the retest capsule |
| `--no-record` | | Do not keep the replay as a retest capsule (a dry run) |
| `--no-link` | | Do not record the retest on the DAG node |

After writing a capsule, `run`, `capture` and `replay` append it to the node's `capsules`
with `dag_update.py --action append`, from the research-dag skill beside this one (or in
`RESEARCH_DAG_BIN`), and print `Recorded on H-001: capsules += <id>`. Without
`research.yaml` or research-dag they print the entry to record by hand.

```bash
python <skills>/experiment-vault/bin/vault.py run --node H-001 --data data/prices.csv --outputs out/ --metrics out/metrics.json --metric accuracy --seed numpy=7 -- python evaluate.py --seed 7
python <skills>/experiment-vault/bin/vault.py replay H-001/20261021T101500Z-9aa09684e0db --pip numpy==2.1.0
python <skills>/experiment-vault/bin/vault.py verify H-001/20261021T101500Z-9aa09684e0db --sha256 <hash from the node> --deep
python <skills>/experiment-vault/bin/vault.py coverage --verify
```

Exit codes:

| Command | Exit |
|---|---|
| `run` | The command's own exit code; a failed run is still recorded. With `--retest-of`, 3 when the command succeeded and the result drifted |
| `replay` | 0 `identical` or `reproduced`; 3 `drifted` (a metric moved beyond the tolerance, or is missing); 1 `failed` (the command exited non-zero) |
| `verify` | 0 when every capsule checked is intact, 1 when any fails (each printed `FAIL`) |
| `coverage` | 1 when `--verify` finds a capsule that fails, or `--strict` finds a result node with no capsule; otherwise 0 |
| any | 2 on an error, printed as `Error: ...` to stderr, and on an argument error |

## literature-discovery tools

In `<skills>/literature-discovery/bin/`. Need requests and PyYAML, and the network.

| Tool | Flags | Output |
|---|---|---|
| `openalex_discovery.py` | `--query TEXT` (required), `--limit N` (default 10), `--output FILE` | Works from OpenAlex by relevance: id, title, year, authors, citations, DOI, abstract index, open access |
| `s2_ranking.py` | `--query TEXT` (required), `--limit N` (default 10), `--api-key KEY`, `--output FILE` | Papers from Semantic Scholar, sorted by influential citations |
| `sota_baseline.py` | `--query TEXT` (required), `--limit N` (default 10), `--output FILE` | A `project_baseline` with the top Semantic Scholar paper, a metric placeholder and the standard setup paths, plus `related_works` |

Without `--output` each prints YAML to the terminal. A failed request prints
`Error fetching from OpenAlex: ...` or `Error fetching from Semantic Scholar: ...` and exits 1.

```bash
python <skills>/literature-discovery/bin/sota_baseline.py --query "graph neural networks drug discovery" --limit 5 --output baseline.yaml
```

## research: scripts/pool.py

The hypothesis pool and retest campaigns on the board ([pool](../skills/research/references/pool.md)). It reads `research.yaml`'s `pool:` section and runs the thread skill's CLI.

| Command | Options | Effect |
|---|---|---|
| `offer` | `--campaign ID`, `--dry-run` | Post every node that may start now and is not on the board: research nodes whose parents are resolved, or campaign nodes whose ancestors have their verdicts. A node with `runner` goes to that role |
| `status` | `--campaign ID` | Held (by whom), offered, ready to post, waiting (on what) and done; a campaign's verdict counts |
| `check NODE` | `--campaign ID` | Exit 0 when an agent may work on the node: it may start, and nothing in its chain is held |
| `record NODE` | `--campaign ID`, `--verdict reproduced\|rebuilt\|differs\|unverifiable`, `--capsule ID`, `--note`, `--agent` | Append the verdict to the node's `retests`; `differs` makes the node `contested` |
| `revisit` | `--campaign ID` | The unverifiable nodes, the most depended on first |
| `review` | `--campaign ID`, `--json`, `--no-board` | One snapshot of every hypothesis: summary, what waits on a person, and each node with its result, evidence, where it ran and pool state. The JSON (`research-review/1`, `skills/research/schemas/review.schema.json`) is what mission control reads |

## research: scripts/reconcile.py

```text
python <skills>/research/scripts/reconcile.py [options]
```

| Flag | Default | Meaning |
|---|---|---|
| `--dag FILE` | `research/hypothesis-dag.yaml` | The DAG |
| `--cwd DIR` | `.` | Where predicates run |
| `--timeout SECONDS` | 60 | Per predicate |
| `--migrate` | | Give every node without one a default `adoption` block, keeping comments and line endings, then exit |
| `--strict` | | Also fail on `unverified_claim` |
| `--json` | | Machine-readable report |

Exit 0 no drift; 1 any finding other than `unverified_claim` (or any finding under
`--strict`); 2 DAG not found or PyYAML missing. Predicates run through the system shell:
`cmd.exe` on Windows, `/bin/sh` elsewhere. Finding kinds are in
[finding-kinds.md](../skills/research/references/finding-kinds.md).

## research: scripts/audit_verify.py

```text
python <skills>/research/scripts/audit_verify.py --action {verify,report} [--clean-room]
```

Reads `metadata.yaml` in the working directory, so run it from the work item folder.

| Flag | Meaning |
|---|---|
| `--action verify` | Check performance improved on the parent (lower is better), and that the deliverables exist (`*-blog.md` and `*-arxiv.md`, or `*-pivot.md`, in `deliverables/` or the working directory). Exit 1 when the audit fails |
| `--action report` | Print the recorded figures without checking them |
| `--clean-room` | With `verify`: also fail if `performance/benchmarks/` differs from `main` |

## research: scripts/discovery.py

```text
python <skills>/research/scripts/discovery.py [--confirm]
```

Run from the workspace root. Greps `README.md` for objectives and `src/` and
`performance/` for metric names, reads the last ten commits, and proposes H-000 and H-001.
It asks before writing `hypothesis-dag.yaml` in the current directory; `--confirm`
accepts without asking. Without a terminal and without `--confirm` it writes nothing. The
greps use the shell, so on Windows they find nothing unless `grep` is on the path; the
agent running `/research init` does the real excavation.

## Repository scripts

For contributors, from the repository root:

| Command | Checks |
|---|---|
| `node scripts/validate-skills.mjs skills` | Each `SKILL.md` against the Agent Skills specification, and that relative links resolve |
| `node scripts/validate-bundle.mjs .` | `bundle.json` against its schema and the skills |
| `node scripts/validate-bundle.mjs --run-checks <workspace> <repo>` | Runs every skill's post-install check in a workspace |
| `python -m unittest discover -s tests -v` | The DAG store, `dag_update` and experiment vault tests |
| `skills-ref validate skills/<name>` | The specification's reference validator; see the README |
