# The capsule format

```
<vault>/VAULT.md                                          the format, for a reader without the tool
<vault>/blobs/sha256/<hex>                                a file, named by the SHA-256 of its content
<vault>/capsules/<project>/<node>/<stamp>-<hash12>.json   one manifest per run or retest
```

Blob names are flat (no fan-out folders), because object stores have no directories; a local vault uses the same names so the two can be synced. A capsule id is the manifest's `created_at` as `YYYYMMDDTHHMMSSZ`, a hyphen, and the first 12 hex digits of the SHA-256 of the manifest file's bytes. The DAG node records the full hash. Manifests are written with sorted keys and two-space indents, so the same content always hashes the same.

## The manifest

[../schemas/capsule.schema.json](../schemas/capsule.schema.json) is the JSON Schema. Every object with a `sha256` and a `size` is a blob.

| Key | Holds |
|---|---|
| `format` | `experiment-vault/1` |
| `tool`, `created_at`, `host`, `agent`, `note`, `work_item` | Who made it, where, when and why |
| `kind` | `run` (a first capture) or `retest` (a replay, or a run with `--retest-of`) |
| `project` | The project's folder in the vault, usually the DAG store project |
| `node` | `id`; `snapshot` of the node's hypothesis, status, target, metric and parent at capture; `dag_store_commit` |
| `code[]` | `name`, `remote`, `branch`, `commit`, `tree`, `object_format`, `pushed`, `dirty`, `archive` (the tar), `exact`, and when dirty `patch` and `untracked[]`; `submodules` (path to commit); `path` for a second repository, relative to the first |
| `data[]` | `path` relative to the main repository, `sha256`, `size` |
| `environment` | `python` (version, implementation, executable, prefix, platform, machine), `lock` (pip freeze, with `packages` count), `wheels[]` (`file`, `sha256`, `size`), `unpinnable[]`, `conda`, `hardware` (cpu, cores, memory_kb, gpus) |
| `run` | `argv`, `cwd` (relative to the main repository), `env`, `seeds`, `observed` (false for `capture`), `started_at`, `duration_s`, `exit_code`, `stdout`, `stderr`, `metrics_path`, and on a replay `replay` (setup, pip overrides) |
| `outputs[]` | `path`, `sha256`, `size` |
| `metrics` | The metrics JSON as the run wrote it |
| `result` | `metric`, `value`, `target` |
| `tolerance` | `rtol`, `atol`: how close a replay's metrics must be |
| `retest_of`, `comparison` | On a retest: the capsule retested, and `verdict`, per-metric `was`, `now`, `delta`, `ok`, and outputs `identical`, `changed`, `new` |

## Why `exact` matters

A commit id names the code, but a repository can be rewritten, made private or lost. The capsule keeps the tar of the commit, and `exact: true` says the tar's own git tree hash (computed from the files in it, as git would) equals the commit's tree. So the restored code is provably the commit's, without the repository. It is false when `.gitattributes` uses `export-ignore`, `export-subst` or end-of-line conversion; the commit is still recorded, and `show` flags it.
