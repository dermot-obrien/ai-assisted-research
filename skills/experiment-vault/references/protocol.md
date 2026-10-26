# Protocol

The procedure every agent follows to keep and replay experiments, so that any two agents, in any tool, leave the same record. MUST and MUST NOT are requirements; SHOULD is the default, to be departed from only with the reason written in `--note`. `<vault.py>` is `python <skills>/experiment-vault/bin/vault.py`. What each step relies on is in [guarantees](guarantees.md).

## 1. When a capsule is required

1.1. A run MUST be captured when any number it produces will be reported to a person, recorded on a node (`actual_performance`, `evidence`, notes), compared with a target, or used to decide what to try next. Exploratory and debugging runs need not be.

1.2. A reported number MUST come from one capsule. A result over several seeds or folds SHOULD be one command that runs them all and writes one metrics file with the aggregate and each seed; otherwise each seed is its own capsule and the report names every capsule.

1.3. A run that already happened outside the vault MAY be kept with `capture`, with `--note` saying so. If it can still be run, run it again through `run` instead: a `capture` records the command, it does not prove the outputs came from it.

## 2. Before the run

2.1. Full clone. `git rev-parse --is-shallow-repository` MUST print `false` in every repository the run uses; if not, run `git fetch --unshallow`. A shallow clone is kept as a whole snapshot, which works but stores the tree again for every commit.

2.2. Submodules. Every submodule MUST be checked out: `git submodule update --init --recursive`.

2.3. Commit. Every change that affects the run MUST be committed, in every repository the run uses, and the branch SHOULD be pushed. `--allow-dirty` SHOULD NOT be used for a result that will be recorded.

2.4. Inputs. Every file the run reads MUST be inside the main repository, in a folder named with `--data` (git-ignored when large; a symlink to data elsewhere is followed). Data the run would fetch from the network MUST be fetched first, into that folder, by a separate step.

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
<node>: <metric> = <value> against a target of <target>. Capsule <node>/<id>; code <repo>@<commit12> (tag vault/<commit12>); <n> data files; replay tolerance rtol <r>, atol <a>.
```

4.4. A tool warning (a tag that did not push, a commit on no remote branch, an unpinnable package) MUST be passed on to the person in the same report.

## 5. Replaying and retesting

5.1. To reproduce a result: `<vault.py> replay <node>/<id>`. To ask whether it still holds after a change, use the form for the change: `--pip <package>==<version>`, `--setup none`, or a new `run ... --retest-of <node>/<id>` for new code or data ([replaying](replaying.md)). Read the command, paths and seeds from `<vault.py> show <node>/<id>`, never from memory.

5.2. Report the verdict as the tool prints it, with every metric that moved. A `drifted` verdict MUST NOT be retried until it passes; it is a finding. A `failed` replay says nothing about the result: fix why it could not run (a missing system library, a moved path) and replay again.

5.3. Every replay is kept as a retest capsule (the default). `--no-record` is for a dry check only, and its verdict MUST NOT be reported as a retest.

## 6. When something goes wrong

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
| `not initialised, or not reachable` | Check `vault.uri` and the gcloud sign-in; a person creates the bucket ([storage](storage.md)) |

## 7. Never

- Never edit, overwrite, move or delete anything in the vault, or a `vault/*` tag.
- Never record a number as a result without the capsule it came from.
- Never report a retest that was run with `--no-record`, or a `drifted` replay re-run until it passed.
- Never pass a secret with `--env`, or put one in the command line or the console output. Never print, copy or write out `RESEARCH_VAULT_GCP_KEY`; the tool reads it.
- Never hand-write a manifest or a `capsules` entry: copy the one the tool printed.
