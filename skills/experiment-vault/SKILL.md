---
name: experiment-vault
description: "Keep every hypothesis experiment as a self-contained, immutable capsule in cheap cloud storage (a Google Cloud Storage bucket or a folder), so any later agent can restore it and run it again: the exact code at its commit, checked against the git tree, the data the run read, the Python environment and optionally its wheels, the hardware, the command, its seeds, console output, outputs and metrics, linked to the hypothesis node by hash. Replays a capsule in a fresh environment and says whether the result is identical, reproduced within tolerance or drifted, and records the retest. Use when running or recording an experiment for a hypothesis, when asked to reproduce, replay, retest or re-run a prior experiment, to check whether a result still holds after code, data or a library changed, to verify or audit what a result was made from, or to set up or archive the vault."
license: CC-BY-4.0 AND Apache-2.0. Instructions under CC BY 4.0, code under Apache-2.0; see the repository's LICENSE.
compatibility: Python 3.10 or newer with PyYAML, and git. A gs:// vault needs the gcloud CLI, signed in with write access to the bucket. Reads research.yaml when there is one (vault.uri, vault.project or dag_project, dag_path); without it, pass --vault and --project. Records each capsule on the DAG node through the research-dag skill when it is installed beside this one.
metadata:
  author: dermot-obrien
  version: "1.0.0"
  homepage: https://github.com/dermot-obrien/ai-assisted-research
  x-skill-requires: ""
---

# Experiment vault

A result is only as good as the ability to make it again. The DAG records what a hypothesis claimed and what it showed; the vault keeps what it was made from, so that a year later, on another machine, an agent can pull the capsule, rebuild the environment and run the same command on the same bytes. Capsules are never edited and never deleted by agents; old ones drift to archive storage on their own and stay readable.

`<skills>` below is the directory the skills are installed in, so the tool is `<skills>/experiment-vault/bin/vault.py`.

## When to use which command

| The user or flow | Command | Read |
|---|---|---|
| "set up the vault", a new bucket | `vault.py init`, after creating the bucket | [references/storage.md](references/storage.md) |
| Run an experiment for a node | `vault.py run --node <id> --data <in> --outputs <out> --metrics <json> --metric <key> --seed name=value -- <command>` | [references/capturing.md](references/capturing.md) |
| Record a run that already happened | `vault.py capture --node <id> --cmd "<command>" --outputs ... --metrics ...` | [references/capturing.md](references/capturing.md) |
| "reproduce", "replay", "re-run" a prior experiment | `vault.py replay <capsule>` | [references/replaying.md](references/replaying.md) |
| "does it still hold" after a library, data or code change | `vault.py replay <capsule> --setup none` or `--pip <pkg>==<v>`, or `vault.py run ... --retest-of <capsule>` | [references/replaying.md](references/replaying.md) |
| Look at what a result was made from | `vault.py list --node <id> --long`, `vault.py show <capsule>`, `vault.py restore <capsule> --to <dir>` | [references/capsule-format.md](references/capsule-format.md) |
| Check capsules are intact, or which results have none | `vault.py verify <capsule> --sha256 <hash> --deep`, `vault.py coverage --verify` | [references/replaying.md](references/replaying.md) |
| Storage classes, cost, archiving, pulling forward | `vault.py lifecycle` | [references/storage.md](references/storage.md) |

## Rules

1. Commit before you run. A capsule pins a commit; `run` refuses uncommitted changes unless `--allow-dirty`, which stores the difference as a patch and marks the capsule dirty. Push the commit too: `show` flags a commit that is on no remote branch.
2. Run the experiment through `vault.py run`, so the command, its console output, its environment and its outputs are recorded by the tool rather than described afterwards. Use `capture` only for a run that already happened, and say so in `--note`.
3. Name every input with `--data` and every output with `--outputs`, inside the repository (git-ignored if large; a symlink is followed). Name the seeds with `--seed`, and set `PYTHONHASHSEED`.
4. Fix the tolerance a replay must meet (`--rtol`, `--atol`) when you run, as you fix the target before the result is known.
5. Never record secrets: `--env` refuses names that look like keys, tokens or passwords.
6. Never delete, overwrite or edit anything in the vault. A wrong capsule is superseded by a new one with a `--note`, never replaced. Agents get create and read access only ([references/storage.md](references/storage.md)).
7. A replay that drifts is a finding, not an error to retry away: record it (the default), report the metrics that moved, and let the research flow decide whether the node becomes `contested`.

## What is in this skill

| Folder | Holds |
|---|---|
| `bin/` | `vault.py`, and the post-install check |
| `references/` | Capturing, replaying, the capsule format, and storage (buckets, cost, archive) |
| `schemas/` | The capsule manifest's JSON Schema |
