# Replaying and retesting

## Reproduce a prior experiment exactly

```bash
python <skills>/experiment-vault/bin/vault.py list --node H-204.4.16 --long
python <skills>/experiment-vault/bin/vault.py replay H-204.4.16/20261021T101500Z-9aa09684e0db
```

`replay` restores the capsule into `.vault-replay/<capsule id>/` (or `--to`), re-hashing every blob as it arrives, creates a fresh virtual environment from the capsule's lock (from its vendored wheels with no package index, when it has them), sets the recorded environment variables, runs the recorded command in the recorded directory, and compares:

| Verdict | Means | Exit |
|---|---|---|
| `identical` | Every metric equal within the tolerance and every output file byte-identical | 0 |
| `reproduced` | Every metric within the tolerance; some output files differ (timestamps, float formatting) | 0 |
| `drifted` | A metric moved beyond the tolerance, or is missing | 3 |
| `failed` | The command exited non-zero | 1 |

### Volatile outputs: timings and the like

Some outputs differ on every run without the result differing: wall-clock timings (`fit_ms`), a timing log, a hostname. Declare them volatile and the comparison leaves them out, listing them apart, so a replay that repeats the result exactly is `identical` instead of `drifted`:

```yaml
vault:
  volatile:
    keys: ["fit_ms", "*_ms", "timing.*"]   # metric and JSON output keys, by name or dotted path
    outputs: ["logs/*.log"]                # whole output files
```

A JSON output that differs only in volatile keys, at any depth, counts as unchanged; any other change in it is still a change, and a metric outside the volatile keys still decides the verdict. `run` records the declaration in the capsule (`volatile`), so every later replay of it uses it; `--volatile-key` and `--volatile-output` on `run` or `replay` add to it, which is how an older capsule's timings are declared at replay. Declare only what cannot carry the result. A key that is the result, or that a decision reads, is never volatile.

The tolerance is the one fixed at capture (`--rtol`, `--atol`), unless the replay overrides it. The replay is kept as a new capsule of kind `retest`, pointing at the original (`retest_of`) and carrying the comparison, and appended to the node's `capsules`; `--no-record` skips that for a dry run. Use `--python` to choose the base interpreter, ideally the recorded version: `replay` warns when it differs.

## Retest after something changed

The question is usually not "can I make the same number" but "does the finding still hold now that X changed". Each change has its own form:

| What changed | Run |
|---|---|
| A library | `vault.py replay <capsule> --pip numpy==2.1.0`: the pinned environment, with the one package moved |
| The environment as a whole | `vault.py replay <capsule> --setup none`: the current interpreter and its packages, as they are |
| The code | Commit the new code, then `vault.py run --node <id> --retest-of <capsule> ... -- <command>`: a new capture compared with the old one |
| The data | The same, with the new data under the same `--data` path |

Each records a `retest` capsule with its verdict. A `drifted` retest of a `validated` node is evidence against the recorded result: the research flow records it on the node and moves the node to `contested` (`/research retest` in the research skill), and a person decides what it means. Never retry a drifted replay until it passes.

## Restore without running

```bash
python <skills>/experiment-vault/bin/vault.py restore <capsule> --to ./h204-4-16
```

The folder holds `repos/<name>/` (the code at its commit, with the data in place), `env/requirements.lock` and `env/wheels/`, `original-outputs/`, `CAPSULE.json`, and `replay.sh` and `replay.ps1`, which rebuild the environment and run the command by hand.

## Verify

```bash
python <skills>/experiment-vault/bin/vault.py verify <capsule> --sha256 <hash from the DAG> --deep
python <skills>/experiment-vault/bin/vault.py coverage --verify
```

`verify` checks the manifest hashes to its id, matches the hash the DAG recorded when given, and that every blob is present; `--deep` downloads and re-hashes each blob. `coverage` reads the DAG, lists the result nodes with no capsule, and with `--verify` checks every capsule the DAG names. Run `coverage --verify` in housekeeping, and before a node's result is cited.

`--deep` on archived capsules reads every byte at archive retrieval prices ([storage.md](storage.md)); run it on what you are about to rely on, not the whole vault.
