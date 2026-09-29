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
| `/aar-start-research {topic}` | The problem to research |
| `/aar-init-research` | None; works on the current repository |
| `/aar-update-lineage` | What to add or change, in words |
| `/aar-progress-research` | None, or a node id |
| `/aar-start-hypothesis {node_id}` | e.g. `H-001` |
| `/aar-progress-hypothesis {WI_id} {node_id}` | e.g. `WI-042 H-001` |
| `/aar-sync-research-result {node_id} {WI_id}` | e.g. `H-001 WI-042` |
| `/aar-run-audit` | None, or a node id |
| `/aar-reconcile` | None |
| `/aar-housekeep` | None |
| `/research-dag`, `/literature-discovery` | Usually invoked by the other skills |

## aar (installer launcher)

`bin/aar.js`, run as `npx aar` after `npm i github:dermot-obrien/ai-assisted-research`, or
as `node <path to the clone>/bin/aar.js`. It finds AAW's install engine and runs
`aaw install --framework <this repository>` with your options.

| Command | Effect |
|---|---|
| `aar install [options]` | Install AAR into the workspace |
| `aar` | The same as `aar install` |
| `aar --help`, `-h`, `help` | Print usage, exit 0 |
| anything else | `Unknown command`, exit 2 |

| Option | Effect |
|---|---|
| `--no-python` | Skip `python -m pip install -r requirements.txt` |
| `--workspace PATH` | Install into PATH instead of the workspace found from the current directory (the nearest folder with `.git` or `.aaw-config.yaml`) |
| `--yes` | Never prompt for the workspace |

What it does: copies each skill to `.agents/skills/<name>/`; links `.claude/skills/<name>`
at it when `.claude/` exists (a junction on Windows); seeds `research.yaml` if absent;
creates `research/`; installs the Python packages; records `modules.aar` in
`.aaw-config.yaml`. It exits 1 when AAW cannot be found, or when the install finished with
a warning, such as AAW not installed in the workspace or pip failing.

The AAW commands the quick start uses are AAW's own: `aaw install` sets up
`.aaw-config.yaml` and the `/aaw-*` skills, taking `--yes`, `--workspace PATH`,
`--tenant NAME`, `--mode local-fs|cloud` and `--work-items-path PATH`. Do not run
`aaw install --help` to find out: it installs. See the AAW README.

## research-dag tools

In `<skills>/research-dag/bin/`. All need PyYAML and read `research.yaml`.

### dag_update.py

Change the DAG. The only supported way to edit it.

```text
python <skills>/research-dag/bin/dag_update.py --action ACTION [options]
```

| Flag | Used by | Meaning |
|---|---|---|
| `--action {add,update,adopt,relink,set,note}` | all, required | What to do |
| `--dag PATH` | all | The DAG file. Default: `dag_path` from `research.yaml`, else `hypothesis-dag.yaml`; with a DAG store, the view path |
| `--no-store` | all | Edit the YAML file directly even when a DAG store is configured |
| `--parent ID` | `add`, `relink` | The parent of a new node, or the new parent |
| `--hypothesis TEXT` | `add` | The hypothesis |
| `--target NUMBER` | `add` | Target improvement, default 0.0 |
| `--metric NAME` | `add` | Metric; warns if it differs from `metadata.primary_metric` |
| `--node-id ID` | `update`, `adopt`, `relink`, `set`, `note` | The node to change |
| `--status STATUS` | `update` | `pending`, `framed`, `in_progress`, `validated`, `contested`, `ineffective`, `discarded` |
| `--performance NUMBER` | `update` | Sets `actual_performance` |
| `--adoption STATE` | `adopt` | `not_assessed`, `not_applicable`, `not_adopted`, `partial`, `adopted`, `contradicted` |
| `--artefact TEXT` | `adopt` | Where the finding lives in the running system |
| `--verification CMD` | `adopt` | Shell predicate that exits 0 while the claim holds |
| `--adoption-note TEXT` | `adopt` | Why the node is at this state |
| `--field NAME` | `set` | Any field but `id` and `parent` |
| `--value YAML` | `set` | Parsed as YAML: `0.07`, `[a, b]`, `null` |
| `--note TEXT` | `note` | Appended to `notes` |

Required per action: `add` needs `--parent` and `--hypothesis`; `update` needs `--node-id`
and `--status`; `adopt` needs `--node-id` and `--adoption`; `relink` needs `--node-id` and
`--parent`; `set` needs `--node-id`, `--field` and `--value`; `note` needs `--node-id` and
`--note`.

It prints `Added new node: H-001`, `Updated node: H-001`, `Set adoption of H-001 to
'adopted'`, `Moved H-002 under H-003`, `Set evidence of H-001` or `Noted on H-001`. The
plain file is locked with `<dag>.lock` while it is written.

```bash
python <skills>/research-dag/bin/dag_update.py --action update --node-id H-001 --status validated --performance 0.845
python <skills>/research-dag/bin/dag_update.py --action set --node-id H-001 --field evidence --value "notebooks/eval.ipynb"
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
arguments. Prints `warning:` lines for paths not created yet, one line per problem, and
`<skill>: ok` when there are none. Exit 0 correct, 1 problems, 2 usage or environment
error (Python older than 3.10, or an argument).

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

## aar-reconcile: reconcile.py

```text
python <skills>/aar-reconcile/scripts/reconcile.py [options]
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
[finding-kinds.md](../skills/aar-reconcile/references/finding-kinds.md).

## aar-run-audit: audit_verify.py

```text
python <skills>/aar-run-audit/scripts/audit_verify.py --action {verify,report} [--clean-room]
```

Reads `metadata.yaml` in the working directory, so run it from the work item folder.

| Flag | Meaning |
|---|---|
| `--action verify` | Check performance improved on the parent (lower is better), and that the deliverables exist (`*-blog.md` and `*-arxiv.md`, or `*-pivot.md`, in `deliverables/` or the working directory). Exit 1 when the audit fails |
| `--action report` | Print the recorded figures without checking them |
| `--clean-room` | With `verify`: also fail if `performance/benchmarks/` differs from `main` |

## aar-init-research: discovery.py

```text
python <skills>/aar-init-research/scripts/discovery.py [--confirm]
```

Run from the workspace root. Greps `README.md` for objectives and `src/` and
`performance/` for metric names, reads the last ten commits, and proposes H-000 and H-001.
It asks before writing `hypothesis-dag.yaml` in the current directory; `--confirm`
accepts without asking. Without a terminal and without `--confirm` it writes nothing. The
greps use the shell, so on Windows they find nothing unless `grep` is on the path; the
agent running `/aar-init-research` does the real excavation.

## Repository scripts

For contributors, from the repository root:

| Command | Checks |
|---|---|
| `node scripts/validate-skills.mjs skills` | Each `SKILL.md` against the Agent Skills specification, and that relative links resolve |
| `node scripts/validate-bundle.mjs .` | `bundle.json` against its schema and the skills |
| `node scripts/validate-bundle.mjs --run-checks <workspace> <repo>` | Runs every skill's post-install check in a workspace |
| `python -m unittest discover -s tests -v` | The DAG store and `dag_update` tests |
| `skills-ref validate skills/<name>` | The specification's reference validator; see the README |
