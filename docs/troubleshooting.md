<!--
SPDX-FileCopyrightText: 2026 Dermot O'Brien
SPDX-License-Identifier: CC-BY-4.0
-->

# Troubleshooting

Keyed to the messages the tools print. Search this page for the start of the message you
see.

## Installing

AAR has no installer of its own; AI-Assisted Work's `bin/skills.mjs` installs the skills. Its messages start `skills:` or name the skill; AAW's [Installing the skills](https://github.com/dermot-obrien/ai-assisted-work/blob/main/DEPLOYMENT.md) covers the installer itself.

### `note: research says it needs work, which is not installed`

`research` was installed, but the `work` skill it hands work items to is not in `.agents/skills/`. Install it with `node <aaw>/bin/skills.mjs install work`, or add AI-Assisted Work's bundle with `"skills": ["work"]` to `.agents/skills.json` and run `sync`.

### `skills: no bundle at .../bundle.json`

`--bundle` takes a path to a clone of this repository (or its `bundle.json`), not a URL. Clone it first, or name the repository's URL in `.agents/skills.json` and run `sync`.

### `aar: command not found`, or `npx aar install` fails

`aar install` was removed in 3.0.0. Install with `skills.mjs` as in the [README](../README.md#install). To keep the old installer with AI-Assisted Work 4.0.0, pin this repository at the `v2.0.0` tag.

### The skills do not appear in Claude Code

The installer links `.claude/skills/<name>` only when `.claude/` exists in the workspace. Create it and install again; each `installed` line should end `(.claude/skills linked)`. Other agents read `.agents/skills/` directly.

### `ModuleNotFoundError: No module named 'yaml'` (or `requests`)

The installer does not install Python packages. Run `python -m pip install -r requirements.txt` from a clone of this repository, with the same Python the tools run under. If pip fails, its own output says why, often a proxy.

### Old `aar-*` folders are still in `.agents/skills`

`skills.mjs sync` removes only skills it installed itself. Folders left by `aar install` from 2.0.0 or earlier are not in its lock, so delete the `aar-*` ones from `.agents/skills/` and `.claude/skills/` by hand. The `research` skill answers to their names.

Keep `research-dag`: it is a skill again in 4.0.0, and `research` requires it. Installing the 4.0.0 bundle (`skills.mjs install --bundle`, or `sync` with the bundle declared) installs `research-dag` 2.0.0 and `experiment-vault` 1.0.0, replacing an old `research-dag` folder left by `aar install`.

### `note: research says it needs work, research-dag, experiment-vault, which is not installed`

The note names each skill `research` requires that is missing from `.agents/skills/`. `research` 4.0.0 requires `research-dag` and `experiment-vault` as well as `work`. Install `work` as above, and for the other two install the whole bundle rather than one skill: `node <aaw>/bin/skills.mjs install --bundle <clone of this repository>`.

## Post-install check (bin/check.py)

### `research.yaml: not found in ... or above`

No `research.yaml` in the working directory or any parent (or at `RMS_ROOT`). No installer creates it. Run the check from the workspace root, run `/research start` or `/research init` there, or copy `assets/research.yaml.example` from the research or research-dag skill (the same file) to `research.yaml`. The `experiment-vault` and `literature-discovery` checks do not look for it.

### `git is not on PATH. Install it; experiment-vault runs it.`

`vault.py` pins every capsule to a git commit, so it needs git. Install it, and make sure the shell the agent uses can find it.

### `research.yaml: dag_path ... is in ..., which does not exist`

The folder that should hold the file is missing. Create it (`mkdir research`) or correct
the path. The same applies to `node_index_path`.

### `warning: research.yaml: dag_path ... does not exist yet`

Normal in a new workspace: the first hypothesis creates the DAG,
`generate_node_index.py` writes the index, and the `work` skill creates the work items folder.

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

A tool needs a key the file lacks. Add it; `assets/research.yaml.example`, in the research or research-dag skill, has every key.

### `note: research/bin/dag_update.py moved to research-dag/bin/dag_update.py; this path goes in research 5.0.0.`

The DAG tools moved to the research-dag skill in 4.0.0. The old path still works, through a launcher that runs the new copy with the same arguments, until research 5.0.0. Change the command, script or agent prompt to `<skills>/research-dag/bin/<tool>.py`. The same note appears for each moved tool: `dag_store.py`, `generate_node_index.py`, `generate_dashboard.py`, `validate_dag_references.py` and `branch_manager.py`.

### `dag_update.py moved to the research-dag skill, which is not installed beside research.`

An old path was run, and the research-dag skill is not in the same skills folder, so the launcher has nothing to run. Exit 2. Install it as the message says, `node <aaw>/bin/skills.mjs install research-dag --bundle <ai-assisted-research>`, or install the whole bundle.

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
covers `update`, `adopt`, `relink`, `set`, `append` and `note`, and `branch_manager.py`'s
`init` and `handoff`.

### `Error: H-001 capsules is not a list; use --action set.`

`--action append` adds one item to a list field, and that field holds something else, such
as a string. Look at the node: if the value should be a list, set it to one with
`--action set --field capsules --value "[...]"`, keeping what was there, then append.

### `Error: Cannot set 'parent': use --action relink.` / `Cannot set 'id': ids never change.`

`--action set` refuses the two fields that would break the graph, and so does
`--action append` (`Cannot append to 'id': ...`). Use `--action relink` to move a node.

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

### `dag_store: NOT PUSHED: recorded locally only. It goes up with the next successful write or dag_store.py sync.`

The same condition, from `dag_store.py` itself: the commit is in your clone, but every push
attempt failed (offline, no write access, or the remote kept moving). Check you can push to
the store's remote, then run `dag_store.py sync`.

### `dag_store: skipping unreadable event ...` / `dag_store: skipping unreadable line in ...`

An event file in the store, or a line of an archive file, is not valid JSON, usually a
half-written file or a merge conflict left in the clone. Replay skips it, so the DAG is
missing that change. Open the file in the store clone (under `$RESEARCH_DAG_HOME` for a
cloned store), repair it through git, then run `dag_store.py view`.

### `Replay of ... differs from ...:`

`dag_store.py verify --against FILE` found differences, listed below the line. Exit 1.
Straight after `import` it means the import lost something; otherwise the store and the
file have diverged since. Decide which is right: keep the store, or record the file's
edits with `dag_store.py record`.

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

## Experiment vault (vault.py)

Errors print `Error: ...` to stderr and exit 2. The commands and flags are in
[commands](commands.md#experiment-vault-tools); the settings in
[configuration](configuration.md#the-experiment-vault).

### `Error: no vault configured: pass --vault, set $RESEARCH_VAULT, or add vault.uri to research.yaml`

No vault was named. Set `vault.uri` in `research.yaml` for the workspace, or pass `--vault`
before the command (`vault.py --vault ./vault list`). `vault.py` searches upward for
`research.yaml` from the working directory, or reads it at `RMS_ROOT`; run it inside the
workspace.

### `Error: no project: pass --project, or set vault.project (or dag_project) in research.yaml`

Capsules are filed under a project. Set `vault.project` or `dag_project`, or pass
`--project` before the command. Every command that reads or writes capsules needs one;
`init`, `lifecycle` and `coverage` without `--verify` do not.

### `warning: .../research.yaml could not be read (...); ignoring it`

`vault.py` found `research.yaml` but could not parse it, often because PyYAML is not
installed (`PyYAML is not installed. Run: python -m pip install PyYAML`) or the YAML is
malformed. It carries on as if there were none, so `vault.uri` and the project are not read;
fix the cause rather than passing flags around it.

### `Error: project '...' must be letters, digits, '.', '_' or '-'` / `node id '...' must be ...`

Project names and node ids become folder names in the vault, so they cannot hold slashes or
spaces.

### `Error: ... has uncommitted changes. Commit them (the capsule pins a commit), or pass --allow-dirty to store the difference as a patch.`

A capsule records the code by commit, so `run` and `capture` refuse a working tree with
changes or untracked files that are not git-ignored. Changes to the DAG and node index files
named in `research.yaml` do not count. Commit (and push), or git-ignore the folders the run
writes. `--allow-dirty` stores the difference as a patch and marks the capsule dirty; use it
only for a run you will not report.

### `Error: data ... is outside .... Put it (or a symlink to it) inside the repository, git-ignored if it is large, so its path is the same on every replay.`

A `--data` or `--outputs` path is not inside the repository the run starts in, so a replay
could not put it back in the same place. Move the data into the repository (a git-ignored
`data/` folder for anything large), or symlink it there and name the link.

### `Error: data ... does not exist` / `warning: output ... was not written`

A `--data` path is missing, which stops the capture. A missing `--outputs` path is only
warned about, since a failed run may not write it; check the run's console output.

### `Error: ... looks like a secret; a capsule is kept for years, so it is not recorded. Pass secrets to the experiment some other way.`

`--env` names a variable whose name contains `KEY`, `TOKEN`, `SECRET`, `PASSWORD`, `PASSWD`
or `CREDENTIAL`. Leave it out of `--env`; the run still sees it, the capsule just does not
keep it.

### `note: PYTHONHASHSEED is not set, so set and dict-of-str iteration order can differ between runs; set it for bit-identical replays`

The capture goes ahead. Set it before running (`export PYTHONHASHSEED=0`, or
`$env:PYTHONHASHSEED = "0"` in PowerShell) so a replay can be `identical` rather than only
`reproduced`.

### `warning: ... package(s) are installed from a local path or in editable mode and cannot be fetched again by version: ...`

A replay rebuilds the environment from versions, and these packages have none. They are
listed under `environment.unpinnable`. Install them from a commit instead, or add their
repository to the capture with `--repo`. With `--strict` an environment that cannot be
captured fully is an error rather than a warning.

### `Error: submodule ... of ... is not checked out, so its code would be missing`

The repository has a submodule whose files are not there, so the capsule could not hold its code. Run the `git submodule update --init --recursive` the message names, then capture again.

### `warning: N file(s) under --outputs were not written by this run and are not kept as its outputs: ...`

An output folder held files from an earlier run. `run` keeps only the files the run wrote, so the capsule is right; empty output folders before a run so the warning, and the confusion, do not recur.

### `PROBLEM ...` and `not ready: N problem(s)`

`--dry-run` found these problems; each line is one of the messages on this page. Fix them all, and run `--dry-run` again until it prints `ready`.

### `warning: ... is a shallow clone, so its history cannot be bundled; keeping a compressed snapshot ...`

The repository was cloned with `--depth`, so git has no history to bundle. The capsule keeps a compressed tar of the commit instead, which restores the same code but stores the whole tree again for every commit. Run `git fetch --unshallow` (or clone without `--depth`) before the next capture.

### `warning: could not push tag vault/... to origin (...); the vault's bundles still hold the commit`

The tag that protects the commit on the remote could not be pushed, usually for lack of push rights or network. The capsule is still complete: its bundles hold the commit. Push the tag later with `git push origin refs/tags/vault/<commit12>`, or pass `--no-push-tag` to skip the attempt.

### `Error: git bundle failed in ...`

`git bundle create` failed, usually on a corrupt local repository or a missing object; its message follows. Run `git fsck` in the repository named.

### `Error: N bundle(s) of ... need commits the vault does not hold`

A bundle builds on commits that no other bundle in the capsule provides, so the repository cannot be rebuilt. This means a bundle was deleted from `repos/<root>/`. Run `vault.py verify <capsule>`; recover the bundle from the bucket's soft delete if it is recent.

### `Error: ... restored to tree ..., not the recorded ...`

The rebuilt commit's tree is not the one the capsule recorded, so the code is not what ran. Do not trust a replay from it; report the capsule.

### `Error: ... code bundles missing`

`verify` found that bundles the capsule names are gone from `repos/<root>/`. As above, recover them from soft delete, or the capsule's code can no longer be restored from the vault (the tag may still hold it on the remote).

### `warning: the archive of ... differs from commit ...'s tree (export-ignore, export-subst or eol attributes); the commit is still recorded`

`.gitattributes` changes what `git archive` writes, so the tar in the capsule is not the
commit bit for bit and the capsule is marked `exact: false`. Remove those attributes for
files the experiment uses if you need exact code; the commit id is still recorded either way.

### `Error: '...' is not a capsule id (<stamp>-<hash12>)` / `Error: no capsule ... in project ...`

A capsule id is `YYYYMMDDTHHMMSSZ-` and 12 hex digits, such as
`20261021T101500Z-9aa09684e0db`. Copy it from `vault.py list` or from the node's `capsules`,
and give the node too (`H-001/<id>`) to skip the search. A bare id is looked up in the
current project only; check `--project`.

### `Error: capsule .../... is not in ... (project ...)`

No manifest at that node and id in this vault and project. Check `--vault` and `--project`
point where the capsule was written.

### `Error: capsule .../... is corrupt: its manifest hashes to ...` / `blob ... is corrupt`

The bytes in the vault no longer match their names. Do not rewrite or delete anything: report
it to the person who owns the vault. A capsule is never repaired in place; if the run can be
made again, a new capsule supersedes it.

### `FAIL ...: manifest hash ... is not the ... the DAG records`

`verify --sha256` or `coverage --verify` found a capsule whose manifest is not the one the
node recorded. The node's `sha256` is the anchor, since the DAG is in git; find out which is
wrong before relying on the result.

### `FAIL ...: N of M blobs missing: ...` / `Error: blob ... is missing from ...`

The manifest names files the vault does not hold, most often a local vault copied into a
bucket without its `blobs/` folder. Copy the missing blobs from the vault they were written
to (`gcloud storage rsync --recursive --no-clobber`).

### `Error: gcloud is not installed or not on PATH; it is needed for a gs:// vault`

Install the Google Cloud CLI and sign in (`gcloud auth login`, or
`gcloud auth activate-service-account --key-file=...` in a cloud session), with read and
create access to the bucket.

### `Error: could not write gs://...: ...` / `Error: gcloud storage cat ... failed: ...`

gcloud's own message follows: usually no access to the bucket, or not signed in. Agents need
`roles/storage.objectCreator` and `roles/storage.objectViewer` on it; see the
[storage reference](../skills/experiment-vault/references/storage.md).

### `Error: ... exists with different content; refusing to overwrite it`

A manifest already sits at that capsule's path with other bytes. Manifests are write-once,
so `vault.py` never replaces one. Run again; the new capsule gets its own id.

### `Error: ... is not empty`

`restore`, and `replay --to`, need an empty or new folder. Pass a new one. Without `--to`,
`replay` picks a fresh folder itself (`.vault-replay/<capsule id>`, then `-2`, `-3` and so on).

### `Error: --pip needs --setup venv, so the overrides do not change your own environment`

`--pip` installs packages over the capsule's lock, which only makes sense in the fresh
environment `--setup venv` builds. Drop `--setup none`, or drop `--pip` and install the
change in your own environment first.

### `warning: Python X replays a run made with Y`

The interpreter the replay uses is not the version the run was made with. The replay goes on,
but a different Python can change results. Pass `--python` with the recorded version where
you have it.

### `Verdict: drifted` (exit 3) / `Verdict: failed` (exit 1)

`drifted`: a metric moved beyond the tolerance, or is missing; the lines below say which,
was and now. That is a finding, not an error: do not retry until it passes. The retest is
recorded on the node, and `/research retest` decides whether the node becomes `contested`.
`failed`: the command exited non-zero; its stderr is in the retest capsule. It says nothing
about the claim; fix the replay (a missing system library, a moved path) and run it again.

### `note: no research.yaml with the research-dag skill beside this one; record the capsule on the node yourself: {...}`

The capsule was written, but `vault.py` could not append it to the node: there is no
`research.yaml`, or no `research-dag/bin/dag_update.py` beside the experiment-vault skill.
Install research-dag, or set `RESEARCH_DAG_BIN` to the folder holding `dag_update.py`, or
append the printed entry yourself with
`dag_update.py --action append --node-id <node> --field capsules --value '<the entry>'`.

### `warning: could not record the capsule on ...: ...`

`dag_update.py` refused the append; its message follows, often `Node ... not found` or a
`capsules` field that is not a list. The capsule is safe in the vault. Fix the node and
append the entry by hand as above.

### `warning: ... is not in ...`

`--node` names a node the DAG at `dag_path` lacks, so the capsule has no snapshot of the
hypothesis. Check the id; with a DAG store, run `dag_store.py view` first.

### `Error: coverage reads the DAG at research.yaml's dag_path, and there is none here`

`coverage` needs `research.yaml` and the DAG it names. Run it inside the workspace.

### `Error: give the command after --, for example: vault.py run --node H-001 -- python train.py`

`run` takes the experiment's command after `--`. For a run that already happened, use
`capture --cmd "..."`.

## Reference check, index and dashboard

### `FOUND N ORPHANED HYPOTHESIS IDs`

Code or docs mention an id the DAG lacks. Add the node with `dag_update.py`, or correct the
reference; `--fix` prints a stub per id. Exit 1. The check scans only `docs/`, `python/`,
`ml_pipeline/` and `.irregular-timeseries-intent/`.

### `DAG store not cloned here yet; dag_store.py view clones it. Aliases not checked.`

Informational. Run `dag_store.py view` once on this machine.

### `Could not read the DAG store for aliases: ...`

Informational: the reference check itself ran, but the alias listing could not. Run
`dag_store.py view` to see the underlying error.

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

### `PyYAML is required: python -m pip install -r requirements.txt`

The Python on your PATH lacks PyYAML. Run `python -m pip install PyYAML` with that same Python. Exit 2.

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

### `No results found in Semantic Scholar.`

`sota_baseline.py` takes its baseline paper from Semantic Scholar, so it writes nothing.
A preceding `Error fetching from Semantic Scholar` line means the request failed (see
above); otherwise broaden the query.

### `Error fetching from OpenAlex: ...`

Usually the network or a proxy. Set `OPENALEX_EMAIL` to join the polite pool, which is
less often throttled.

## Reconstructing lineage (discovery.py)

### `Non-interactive mode detected. Use --confirm to auto-accept.`

`discovery.py` prints its proposed DAG and asks for confirmation. Without a terminal, as
when an agent runs it, it writes nothing. Read the proposal, then run it again with
`--confirm`. It writes `hypothesis-dag.yaml` in the working directory, not at `dag_path`,
so move the file to `dag_path` if they differ.

## In an agent

### The agent says the `work` skill, or an `/aaw-*` skill, is missing

The research flows that create or run work delegate to AI-Assisted Work's `work` skill
(`/work start`, `/work progress`, `/work initiative`). Install it in the workspace (`node <aaw>/bin/skills.mjs install work`) and restart the agent. Before AI-Assisted Work 4.0.0 the same steps were five skills named `aaw-start-work`, `aaw-progress-work` and so on; those names are retired.

### The agent reads the wrong DAG

It follows `research.yaml`. Check `dag_path` there, and that you opened the workspace
root, not a subfolder with its own `research.yaml`.
