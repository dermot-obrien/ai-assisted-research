---
name: experiment-vault
description: "Keep every hypothesis experiment as an immutable capsule in cheap cloud storage (a GCS bucket or a folder) that any later agent can replay: the code at its commit, as tagged incremental git bundles; the data, or the registered dataset version; the environment and the machine it ran on; the command, seeds, outputs and metrics, linked to the node by hash. Replays a capsule and says whether the result is identical, reproduced or drifted. Registers datasets as append-only, revisable or frozen versions with backtest, sealed holdout and forward windows. Pins runtimes (machine type, Python build, uv lock, determinism settings) so an experiment gives the same result on any machine or agent platform, with a parity check. Use when running, recording, replaying or retesting an experiment, checking a result still holds, auditing what it was made from, registering or windowing a dataset, backtesting or forward-testing a strategy, making results reproducible across machines, or setting up the vault."
license: CC-BY-4.0 AND Apache-2.0. Instructions under CC BY 4.0, code under Apache-2.0; see the repository's LICENSE.
compatibility: Python 3.10 or newer with PyYAML, and git. A gs:// vault needs the gcloud CLI, signed in with write access to the bucket, or a service account key in RESEARCH_VAULT_GCP_KEY (cloud sessions). Reads research.yaml when there is one (vault.uri, vault.project or dag_project, dag_path); without it, pass --vault and --project. Records each capsule on the DAG node through the research-dag skill when it is installed beside this one.
metadata:
  author: dermot-obrien
  version: "1.5.0"
  homepage: https://github.com/dermot-obrien/ai-assisted-research
  x-skill-requires: ""
---

# Experiment vault

A result is only as good as the ability to make it again. The DAG records what a hypothesis claimed and what it showed; the vault keeps what it was made from, so that a year later, on another machine, an agent can pull the capsule, rebuild the environment and run the same command on the same bytes. Capsules are never edited and never deleted by agents; old ones drift to archive storage on their own and stay readable.

`<skills>` below is the directory the skills are installed in, so the tool is `<skills>/experiment-vault/bin/vault.py`.

## Follow the protocol

Every capture and replay follows [references/protocol.md](references/protocol.md), step by step: when a capsule is required, the checks before a run (ending with the same command and `--dry-run`, which must print `ready`), the run, what to verify and how to report it, how to replay and retest, and what to do for each error. It is short; read it before the first run in a session. [references/guarantees.md](references/guarantees.md) says what the vault promises, each promise with the tests that prove it.

## When to use which command

| The user or flow | Command | Read |
|---|---|---|
| "set up the vault", a new bucket | `vault.py init`, after a person creates the bucket | [references/storage.md](references/storage.md) |
| Run an experiment for a node | `vault.py run ... --dry-run -- <command>`, then the same without `--dry-run` | [references/protocol.md](references/protocol.md), [references/capturing.md](references/capturing.md) |
| Record a run that already happened | `vault.py capture --node <id> --cmd "<command>" --outputs ... --metrics ...` | [references/protocol.md](references/protocol.md) 1.3 |
| "reproduce", "replay", "re-run" a prior experiment | `vault.py replay <capsule>` | [references/replaying.md](references/replaying.md) |
| "does it still hold" after a library, data or code change | `vault.py replay <capsule> --setup none` or `--pip <pkg>==<v>`, or `vault.py run ... --retest-of <capsule>` | [references/replaying.md](references/replaying.md) |
| Look at what a result was made from | `vault.py list --node <id> --long`, `vault.py show <capsule>`, `vault.py restore <capsule> --to <dir>` | [references/capsule-format.md](references/capsule-format.md) |
| Check capsules are intact, or which results have none | `vault.py verify <capsule> --sha256 <hash> --deep`, `vault.py coverage --verify` | [references/replaying.md](references/replaying.md) |
| Register data more than one test reads, add a new version, "new data arrived" | `vault.py dataset create`, `dataset add` | [references/datasets.md](references/datasets.md) |
| Backtest, holdout, forward test, out-of-sample, "has this been looked at" | `vault.py dataset window`, `run --dataset <name>@<version>:<mount>:<window>`, `dataset uses` | [references/datasets.md](references/datasets.md) |
| "the data changed", what rests on an old version | `vault.py dataset diff`, `dataset impact <name>@<version>` | [references/datasets.md](references/datasets.md) |
| The same result on any machine or agent platform, "pin the environment", determinism | `vault.py runtime create`, `runtime check`, `run` on a node with `runtime`, `parity` | [references/runtimes.md](references/runtimes.md) |
| Storage classes, cost, archiving, pulling forward | `vault.py lifecycle` | [references/storage.md](references/storage.md) |

## Rules

1. Follow [the protocol](references/protocol.md). Its MUST and MUST NOT lines are not optional.
2. A number is a result only with the capsule it came from, verified against the hash on the node, and cited by its id.
3. Commit, in a full clone with submodules checked out, before you run, and run through `vault.py run`; `--dry-run` first must print `ready`.
4. Never edit, overwrite or delete anything in the vault or a `vault/*` tag, and never record a secret. A wrong capsule is superseded by a new one with a `--note`.
5. A replay that drifts is a finding, not an error to retry away: report the metrics that moved, and let the research flow decide whether the node becomes `contested`.
6. A test's evidence is only as good as the data it could have seen. Run on the window the framing fixed, look at a sealed holdout once, and leave revising an append-only dataset or overriding a holdout to a person ([protocol](references/protocol.md) section 6).

## What is in this skill

| Folder | Holds |
|---|---|
| `bin/` | `vault.py`, and the post-install check |
| `references/` | The protocol agents follow, the guarantees and the tests behind them, capturing, replaying, datasets and their windows, runtimes and deterministic experiments, the capsule format, and storage (buckets, cost, archive) |
| `schemas/` | The capsule manifest's JSON Schema |
