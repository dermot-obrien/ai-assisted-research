# Capturing an experiment

The steps an agent follows, in order, are in [the protocol](protocol.md); this page explains what a capture records and why. Before a real run, run the same command with `--dry-run`: it checks everything below and changes nothing.

`vault.py run` runs the experiment and keeps everything it used and produced. Run it from the repository the experiment lives in (or pass `--cwd`), after committing.

```bash
export PYTHONHASHSEED=0
python <skills>/experiment-vault/bin/vault.py run --node H-204.4.16 \
  --data data/prices.csv --outputs out/ --metrics out/metrics.json --metric accuracy \
  --seed numpy=7 --seed torch=7 --rtol 1e-6 \
  --note "walk-forward revalidation" --agent my-agent --work-item WI-042 \
  -- python evaluate.py --seed 7
```

PowerShell is the same with `$env:PYTHONHASHSEED = "0"` and a backtick for each line break.

## What it records

| Recorded | How |
|---|---|
| The code | The main repository's commit, tree, branch and remote. The commit is tagged `vault/<commit12>` and the tag pushed to `origin` (`--no-push-tag` keeps it local), and the vault gets a git bundle of only the commits it does not hold yet, so a new capture of a known repository costs kilobytes. Restore rebuilds the repository from the bundles and proves the tree. A shallow clone, or `--code-storage archive`, keeps a compressed snapshot instead ([capsule format](capsule-format.md#how-the-code-is-kept)). Every submodule is captured too, as its own entry, and must be checked out. Add `--repo <path>` for every other repository the run imports. The end-of-line settings the files were checked out with are recorded, so a restore writes the same bytes. |
| The data | Every file under each `--data` path, by SHA-256. Data must sit inside the main repository so its path is the same on replay; put large data in a git-ignored folder, or symlink it there. |
| The environment | The interpreter (`--python`, default the one running `vault.py`): version, implementation, platform; `pip freeze --all` as the lock; a conda export when a conda environment is active; the CPU, cores, memory and GPUs. With `--vendor-wheels` (or `vault.vendor_wheels: true`), the wheel of every pinned package too, so a replay installs with no package index at all. |
| The run | The command, the directory it ran in, `--seed` values, the environment variables that change results (`PYTHONHASHSEED`, thread counts, `CUDA_VISIBLE_DEVICES`, `TZ`, locale, and any `--env NAME`), start time, duration, exit code, and stdout and stderr in full. |
| The outputs | Every file under each `--outputs` path that the run wrote (a file left from an earlier run is skipped, with a warning), and the `--metrics` JSON, parsed. `--metric` names the key (dotted for nested) that is the node's result; the target comes from the node, or `--target`. |
| The node | The node's id, a snapshot of its hypothesis, status, target and metric, and the DAG store commit the view was generated from. |

A failed run is still recorded, with its exit code: a crash is part of the history. `run` exits with the command's own exit code.

## Uploading and linking

Blobs are uploaded first, skipping any the vault already holds, so a dataset or a wheel shared by a hundred capsules is stored once. The manifest is written last, with a precondition that fails if the object exists, so a manifest never points at a blob that is not there and is never replaced.

The capsule is then appended to the node's `capsules` list through the research-dag skill (`dag_update.py --action append`), with its id, full SHA-256, URI, kind and result. Without research.yaml or research-dag, `vault.py` prints the entry to record by hand. `--no-link` skips it.

## Wheels: when to vendor

`pip freeze` pins versions, and PyPI keeps old releases, so the lock alone usually rebuilds the environment. Vendoring removes the "usually": a yanked release, a deleted package, a private index that moved, or a machine with no network. The cost is one copy of each wheel version across the whole vault. Vendor for any result that a decision, a paper or a product rests on. Packages installed editable or from a local path cannot be fetched by version: `run` warns and lists them under `environment.unpinnable`; install them from a commit instead, or add their repository with `--repo`.

## What a capsule cannot pin

Bit-identical replay also needs the same hardware and drivers for GPU work, deterministic kernels (`torch.use_deterministic_algorithms(True)`, `CUBLAS_WORKSPACE_CONFIG`), and no live inputs. The capsule records the hardware so a difference is visible, the tolerance says how close is close enough, and anything the run fetched from the network at run time (an API, a live price feed) is not in the capsule unless the run wrote it to a `--data` or `--outputs` path. Make the experiment download into a data folder in one step and run on that folder in the next.
