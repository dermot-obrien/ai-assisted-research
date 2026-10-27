# Datasets

A dataset that more than one test reads is registered in the vault once, as numbered versions, and every capsule that reads it records the version it read instead of copying its files. The dataset's rule says how it may change, its windows say which part of it a test may look at, and the window a test ran on decides what its result is worth as evidence. `<vault.py>` is `python <skills>/experiment-vault/bin/vault.py`. This page explains; the steps an agent follows, and which are a person's, are [the protocol](protocol.md), section 6.

Backtesting is hypothesis testing on history. What makes a backtest weak evidence is that the history was there while the strategy was designed, so it can be fitted to it, knowingly or not. The vault cannot see intent, but it can record, and enforce, which data a test could have seen: data named for backtesting, a sealed holdout looked at once, or data that did not exist when the test was fixed.

## A dataset and its versions

```bash
<vault.py> dataset create prices-eod --rule append-only --title "Daily closes" \
  --source "https://vendor.example/eod" --licence "vendor terms" --owner research
<vault.py> dataset add prices-eod --from /data/prices-eod --source "vendor pull 2026-10-27" \
  --fetched-by "fetch_eod.py@3f2a9c1" --source-checksums /data/prices-eod.sha256 --note "first pull"
```

`dataset create` writes the dataset's description once: its rule, title, sources, licence and owner. `dataset add` scans the whole folder, compares it with the latest version and, if anything differs, writes the next version, `v0001`, `v0002`, ...: every file's path, hash and size, what was added, extended, changed or removed since the version before, and where the data came from (`--source`, `--fetched-by`, the checksums the source publishes). Each file is stored once in the vault's blobs, so a version that extends one file stores the extended file and nothing else again. A version is never rewritten; an unchanged folder adds no version.

| Rule | A new version may | Use it for |
|---|---|---|
| `append-only` | add files, and extend a file at its end (the old file is a byte prefix of the new one) | Data that only accumulates: prices, trades, sensor logs |
| `revisable` | also change or remove files, as a revision with `--revise "<reason>"` | Data that is corrected or re-derived: a cleaned table, labels |
| `frozen` | nothing: one version only | A published benchmark, a fixed split |

An append-only dataset is never revised by an agent. When its history really is wrong (a vendor's correction), a person runs `dataset add ... --revise "<reason>" --allow-append-only-revision` at a terminal and types the dataset's name to confirm; the tool refuses without a terminal, and whenever `CI` is set. A revision prints every capsule built on an earlier version, which `dataset impact <name>@<version>` lists again at any time: those results are retested on the new version (`/research retest`), or say which version they rest on.

`dataset show <name>` gives the description, the versions and the windows; `dataset show <name>@<version> --files` every file; `dataset diff <name>@v0001 <name>@v0003` what changed; `dataset fetch <name>@<version> [--to <folder>]` a hash-checked copy; `dataset uses <name>` every capsule that read it, and `dataset list` every dataset.

## Windows

A window is a named part of a dataset, defined once, before the tests that use it:

```bash
<vault.py> dataset window prices-eod is-2015-2022 --class backtest --from-date 2015-01-01 --to-date 2022-12-31
<vault.py> dataset window prices-eod oos-2023 --class holdout --from-date 2023-01-01 --to-date 2023-12-31
<vault.py> dataset window prices-eod live --class forward --from-version v0007
```

| Class | Is | Gives |
|---|---|---|
| `backtest` | A span of history named for development and backtesting | Evidence the design may have been fitted to |
| `holdout` | A sealed span of history no backtest window overlaps | One look per node, and none for a sibling of a node that looked |
| `forward` | Everything an append-only dataset gains after a version | Data that did not exist when the test was fixed |

Dates are the data's own dates, compared as ISO text. The vault does not cut files by date: the run is told its window and reads only that part (below), and the capsule records which window it was told, so an audit can check it did. A forward window gives the run, for each file, the byte where the data after `--from-version` starts, so the run reads only the new rows of a file that grew.

## Running on a dataset

```bash
<vault.py> run --node H-12.3 --dataset prices-eod@latest:data/prices-eod:oos-2023 \
  --outputs out --metrics out/metrics.json --metric sharpe --seed numpy=7 --dry-run -- python backtest.py --seed 7
```

`--dataset <name>@<version>:<mount>[:<window>]` (repeatable) resolves the version (`latest` is the newest when the run starts), fetches it once into a local read-only cache (`~/.cache/experiment-vault`, or `RESEARCH_VAULT_CACHE`), hash-checked, and links it at `<mount>`, a git-ignored folder inside the repository. The run finds each dataset in the JSON file named by the environment variable `VAULT_DATASETS`:

```json
{"prices-eod": {"version": "v0009", "path": "/abs/repo/data/prices-eod",
                "window": {"window": "oos-2023", "class": "holdout", "from_date": "2023-01-01", "to_date": "2023-12-31"},
                "forward_offsets": null}}
```

The capsule records the dataset, version, the hash of the version's record, the mount and the window, and not the files: they are in the version already. Restore and replay fetch the same version and link it at the same mount, and refuse if the version's record no longer hashes to what the capsule recorded; `verify` checks the record and every file's blob. A run that writes into its dataset is caught after it ends, and nothing is recorded.

## Sealed holdouts

A holdout window is sealed. Before the run starts, the vault writes a claim for the node, and refuses the run when the node, or a sibling of it in the DAG (a node with the same parent), already has one: a holdout tells you something only the first time you look, and a sibling that saw how its sibling did is not looking for the first time. A node with another parent may look. The claim is written before the run, so a run that fails still spends the look; get the run right on a backtest window first. `--dry-run` checks the claim and spends nothing.

The node must be in the DAG (refresh the view), so its siblings can be found. Once a dataset has a holdout window, every run on it names a window: a run told the whole dataset could read the holdout. A person may override a spent look with `--override-holdout "<reason>"`, at a terminal, typing the dataset's name; the override is kept with the claims, and `dataset uses <name> --window <window>` shows every claim and override.

## Evidence classes

Every capsule records an evidence class, which the research flows read when they set a node's status (the research-dag skill's `references/node-schema.md`):

| Class | When | Can move a node to |
|---|---|---|
| `exploratory` | The run was given `--exploratory` | nothing past `in_progress` |
| `untracked` | No window: a registered dataset read whole, or only `--data` | `validated` or `ineffective`, for a node that fixed no window |
| `backtest` | A backtest window | `backtested`, or `validated` for a node whose framing fixed only a backtest |
| `holdout` | A holdout window | `holdout_passed` |
| `forward` | A forward window | `forward_testing`, and `validated` or `retired` at the checkpoints framing fixed |

One test has one class: windows of different classes in one run are refused. A test of a trading strategy is framed with its windows and its decision rule (the backtest target, the holdout target, the forward checkpoints and the rule that retires it), before any of them is run.

## Continuous testing

A forward test is the same command run again as data arrive. Each `dataset add` of new data makes a version; each run of the node's command on `<name>@latest:<mount>:<forward window>` is a capsule of class `forward` on the newest version, recorded on the node beside the earlier ones. Compare each with the checkpoints fixed at framing, and move the node to `validated`, `contested` or `retired` by them, never by a rule chosen after seeing the numbers.

## Never

- Never revise an append-only dataset, override a holdout, or confirm as a person: those are a person's, at a terminal.
- Never read a dataset with a holdout outside the window the run names, or a forward window before its offsets.
- Never write into a mounted dataset, or edit a file in the cache; write outputs under `--outputs`.
- Never put data a later test depends on only in a capsule's `--data` when another test reads it too: register it.
