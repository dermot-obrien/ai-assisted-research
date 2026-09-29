<!--
SPDX-FileCopyrightText: 2026 Dermot O'Brien
SPDX-License-Identifier: CC-BY-4.0
-->

# Troubleshooting

Keyed to the messages the tools print. Search this page for the start of the message you
see.

## Installing

### `depends on "aaw" which is not installed — install it first`

`aar install` found AAW's engine but AAW is not installed in this workspace. The skills
were still installed, but the command exits 1. Run `npx aaw install --yes` (or
`node .ai-assisted-work/bin/aaw.js install --yes`), then `npx aar install` again.

### `AAR requires AAW (it provides the shared install engine)`

The launcher could not find AAW at all. Install it with
`npm i github:dermot-obrien/ai-assisted-work`, or clone it to `.ai-assisted-work`, then
re-run. Installing AAR with `npm i github:dermot-obrien/ai-assisted-research` fetches AAW
as its dependency.

### `Unknown command: ...`

`aar` takes only `install` (or nothing) and `--help`. Exit 2.

### The skills do not appear in Claude Code

The installer links `.claude/skills/<name>` only when `.claude/` exists in the workspace.
Create it and run `npx aar install` again; the output should include
`claude: linked 12 → .claude\skills/`. Other agents read `.agents/skills/` directly.

### `claude: copied 12 → .claude/skills/ (links unavailable)`

The filesystem refused both a symlink and a junction, so the skills were copied. It works,
but an edit under `.claude/skills/` does not reach `.agents/skills/`. Re-install after
upgrading rather than editing either copy.

### `python not found on PATH — skipped dependency install`

The installer could not run pip. Install Python 3.10 or newer, then
`python -m pip install -r node_modules/ai-assisted-research/requirements.txt` (or the
path the message gives).

### `pip install failed (exit N) for requirements.txt`

pip could not install PyYAML or requests; its own output above says why, often a proxy.
Fix that and run `python -m pip install pyyaml requests`.

### Red `NativeCommandError` text in PowerShell during install

Windows PowerShell 5.1 shows anything pip writes to stderr, such as
`WARNING: Ignoring invalid distribution`, as a red error record. If the install ends with
`Done. aar@... — 12 skill(s).` and exits 0, it worked.

## Post-install check (bin/check.py)

### `research.yaml: not found in ... or above`

No `research.yaml` in the working directory or any parent (or at `RMS_ROOT`). Run the
check from the workspace root, run `npx aar install` there, or copy
`research-dag/assets/research.yaml.example` to `research.yaml`.

### `research.yaml: dag_path ... is in ..., which does not exist`

The folder that should hold the file is missing. Create it (`mkdir research`) or correct
the path. The same applies to `node_index_path`.

### `warning: research.yaml: dag_path ... does not exist yet`

Normal in a new workspace: the first hypothesis creates the DAG,
`generate_node_index.py` writes the index, and AAW creates the work items folder.

### `research.yaml: work_items_path is not set` (or `dag_path`, `node_index_path`)

Add the key, as a path relative to `research.yaml`. See
[configuration](configuration.md#researchyaml).

### `PyYAML is not installed for this Python` / `requests is not installed`

Install it for the Python that runs the tools: `python -m pip install PyYAML requests`.
Where several Pythons are installed, `python -m pip` makes sure it is the same one.

### `Python 3.x is too old: the research tools need 3.10 or newer.`

Install a newer Python and make it the one `python` runs. Exit 2.

### `usage: check.py (run from the workspace root; takes no arguments)`

The check takes no arguments. Exit 2.

## Changing the DAG (dag_update.py)

### `research.yaml not found. Looked upward from: ...`

Printed at the end of a traceback by the tools that need `research.yaml`
(`generate_node_index.py`, `generate_dashboard.py`, `validate_dag_references.py`,
`dag_store.py`). Run from inside the workspace, or set `RMS_ROOT` to its root.

### `RMS_ROOT=... has no research.yaml`

`RMS_ROOT` is set but points at the wrong folder. Correct or unset it.

### `research.yaml missing key: dashboard.experiments_dir`

A tool needs a key the file lacks. Add it; the seeded example has every key.

### `Error: DAG file not found at hypothesis-dag.yaml`

`dag_update.py` found no `research.yaml`, so it looked for `hypothesis-dag.yaml` in the
working directory. Run it inside the workspace or pass `--dag research/hypothesis-dag.yaml`.
With a path other than `hypothesis-dag.yaml`, the file at `dag_path` does not exist yet:
create it with a root node, as in the [quick start](quick-start.md#4-write-a-tiny-dag).

### `Error: Parent H-009 is not in the DAG.`

`--parent` names a node that does not exist. Check the id against the DAG or the node
index.

### `Error: Node H-009 not found.`

`--node-id` names a node that does not exist.

### `Error: --parent and --hypothesis are required for 'add' action.`

Each action has required flags; see [commands](commands.md#dag_updatepy). The same form
covers `update`, `adopt`, `relink`, `set` and `note`.

### `Error: Cannot set 'parent': use --action relink.` / `Cannot set 'id': ids never change.`

`--action set` refuses the two fields that would break the graph. Use `--action relink`
to move a node.

### `Error: Cannot move H-000 under its own descendant H-001.`

A relink would create a cycle.

### `argument --status: invalid choice: 'done'`

Statuses are `pending`, `framed`, `in_progress`, `validated`, `contested`, `ineffective`
and `discarded`. Exit 2.

### `Warning: Proposed metric 'f1' differs from DAG's primary metric 'accuracy'.`

The node was added, but measures something other than the DAG's primary metric. Either
the node is wrong or it needs its own justification; comparisons across metrics are not
valid.

### `Warning: H-001 claims 'adopted' with no --verification predicate.`

The adoption was recorded, but `reconcile.py` will report it as `unverified_claim`. Record
a predicate with `--verification`.

### `Could not acquire DAG lock at ...hypothesis-dag.yaml.lock. Another agent might be updating it.`

Another `dag_update.py` holds the lock, or one crashed and left the file. If nothing else
is running, delete the `.lock` file.

## The shared DAG store (dag_store.py, dag_update.py)

### `Warning: research.yaml sets only one of dag_store and dag_project; editing the YAML file directly.`

Set both keys to use the store, or neither.

### `Error: research.yaml needs both dag_store and dag_project to use the DAG store`

A `dag_store.py` command needs both keys, or `--store` and `--project`.

### `Error: no research.yaml found; pass --store and --project`

Run inside the workspace, or name the store on the command line.

### `Error: dag_store ... is neither a clone nor a repository to clone`

The path is not a git work tree or a bare repository. Correct it, or use a URL. On
Windows, a Git Bash path such as `/c/Users/me/dags.git` shows as `resolved to
C:\c\Users\...`, because Python does not read Git Bash paths: write `C:/Users/me/dags.git`
instead. The same applies to `RESEARCH_DAG_HOME` and `RMS_ROOT`.

### `Error: dag_project must be a plain folder name`

No slashes or special characters in `dag_project`.

### `Error: could not clone ...`

git could not reach the store; git's message follows. Check the URL and your credentials.

### `Error: project ... already has events; import seeds an empty project only`

The project was seeded already. Use `dag_store.py view` to get the DAG, or pick a new
`dag_project`.

### `Error: replay does not reproduce the imported DAG; nothing was committed`

The DAG holds something the event format cannot round-trip; the lines after the message
name the differences. Fix them in the file and import again.

### `Error: nodes cannot be removed from the DAG store`

The store is append-only. Set the node's status to `discarded` instead.

### `The change is recorded in the local store only; dag_store.py sync pushes it.`

The push failed, often because you are offline. Run `dag_store.py sync` later; the next
write also pushes it.

### `Added new node: H-204.4.25b (H-204.4.25 was taken by a concurrent writer; the alias is recorded)`

Someone added a node under the same id first. Use the id printed. `validate_dag_references.py`
and `dag_store.py report` list the alias.

### `Note: H-101 status was changed concurrently to ...; this change replaced it.`

Two writers changed one field; yours was later and won. Check the replaced value was not
the one you wanted.

### An edit to hypothesis-dag.yaml disappeared

With a store, the file is a generated view and every write regenerates it. Run
`dag_store.py record` before the next write to turn direct edits into events. Tools that
rewrite the file themselves, such as `reconcile.py --migrate`, need `record` afterwards.

## Reference check, index and dashboard

### `FOUND N ORPHANED HYPOTHESIS IDs`

Code or docs mention an id the DAG lacks. Add the node with `dag_update.py`, or correct the
reference; `--fix` prints a stub per id. Exit 1. The check scans only `docs/`, `python/`,
`ml_pipeline/` and `.irregular-timeseries-intent/`.

### `DAG store not cloned here yet; dag_store.py view clones it. Aliases not checked.`

Informational. Run `dag_store.py view` once on this machine.

### The dashboard page is blank

The graph loads D3 from `d3js.org`; open the page with a network connection. If the
connection is fine, the browser console names the record that broke the script.

### A node is missing from `ready`

Its parent is not resolved (it is under `blocked` with `blocked_by`), it is not `pending`,
or the index is stale. Run `generate_node_index.py`.

## Adoption check (reconcile.py)

Finding kinds, in the order reported:

| Kind | What to do |
|---|---|
| `drift` | A predicate that held no longer does, or could not run. Its output follows. Raise work to restore the finding or update the node |
| `validated_contradicted` | The system does what a validated node warns against. Raise work |
| `validated_not_adopted` | Validated, nothing in `blocked_by`, not adopted. Adopt it or record the blocker |
| `unverified_claim` | `adopted`, `partial` or `contradicted` without `verification`. Add a predicate. Fails only under `--strict` |
| `unknown_blocker` | `blocked_by` names a node that does not exist |
| `unknown_contester` | `contested_by` names a node that does not exist |
| `no_adoption_block` | Never assessed. Run `--migrate` |

### `DAG not found: research/hypothesis-dag.yaml`

Pass `--dag` with the DAG's path. Exit 2.

### `predicate timed out after 60s`

Reported as `drift`. The predicate hung, often on a quoting mistake. Raise `--timeout`
only if the check is genuinely slow.

### A predicate passes on Linux but drifts on Windows

Predicates run through `cmd.exe` on Windows, where `grep` and single quotes do not work as
in a Unix shell. Write predicates that run in both, for example
`python -c "import sys; sys.exit('day_of_week' not in open('src/features.py').read())"`.

### `migrate: node set changed; file left as written, inspect the diff`

`--migrate` found the file changed shape after adding blocks. Inspect `git diff` and
restore the file if needed.

## Audit (audit_verify.py)

### `Error: metadata.yaml not found at metadata.yaml`

Run it from the work item folder that holds the node's `metadata.yaml`.

### `[FAIL] Benchmark directory performance/benchmarks not found. Cannot verify clean room.`

`--clean-room` needs the benchmarks under `performance/benchmarks/`, relative to the
working directory.

### `Clean Room Failure: The benchmark scripts in performance/benchmarks have been modified compared to the 'main' branch.`

The evaluation code on the branch differs from `main`. That is what the check exists to
catch: audit with the `main` version.

### `Warning: Performance did not improve (0.84 >= 0.81).`

The verifier assumes lower is better. For a metric where higher is better, such as
accuracy, read the verdict the other way round, or record performance as an error.

## Literature discovery

### `Error fetching from Semantic Scholar: 429 Client Error`

Semantic Scholar's unauthenticated rate limit. Wait and retry, or set `S2_API_KEY`.
`sota_baseline.py` depends on Semantic Scholar, so it fails with it; use
`openalex_discovery.py` meanwhile.

### `Error fetching from OpenAlex: ...`

Usually the network or a proxy. Set `OPENALEX_EMAIL` to join the polite pool, which is
less often throttled.

## In an agent

### The agent says an `/aaw-*` skill is missing

The `aar-*` skills that create or run work delegate to AI-Assisted Work. Install AAW in
the workspace (`npx aaw install`) and restart the agent.

### The agent reads the wrong DAG

It follows `research.yaml`. Check `dag_path` there, and that you opened the workspace
root, not a subfolder with its own `research.yaml`.
