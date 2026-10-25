# The capsule format

```
<vault>/VAULT.md                                          the format, for a reader without the tool
<vault>/blobs/sha256/<hex>                                a file, named by the SHA-256 of its content
<vault>/repos/<root commit>/<tip commit>.bundle           a repository's history, as incremental git bundles
<vault>/capsules/<project>/<node>/<stamp>-<hash12>.json   one manifest per run or retest
```

Blob names are flat (no fan-out folders), because object stores have no directories; a local vault uses the same names so the two can be synced. A capsule id is the manifest's `created_at` as `YYYYMMDDTHHMMSSZ`, a hyphen, and the first 12 hex digits of the SHA-256 of the manifest file's bytes. The DAG node records the full hash. Manifests are written with sorted keys and two-space indents, so the same content always hashes the same.

## The manifest

[../schemas/capsule.schema.json](../schemas/capsule.schema.json) is the JSON Schema. Every object with a `sha256` and a `size` is a blob.

| Key | Holds |
|---|---|
| `format` | `experiment-vault/2`; format 1 (code kept only as a plain tar) is still read |
| `tool`, `created_at`, `host`, `agent`, `note`, `work_item` | Who made it, where, when and why |
| `kind` | `run` (a first capture) or `retest` (a replay, or a run with `--retest-of`) |
| `project` | The project's folder in the vault, usually the DAG store project |
| `node` | `id`; `snapshot` of the node's hypothesis, status, target, metric and parent at capture; `dag_store_commit` |
| `code[]` | `name`, `remote`, `branch`, `commit`, `tree`, `object_format`, `pushed`, `dirty`, `exact`, and `storage`: `bundle` with `root` (the repository's root commit), `bundles` (the tip commits of the bundles that hold it), `tag` and `tag_pushed`, or `archive` with `archive` (a `tar.gz` of the commit, a plain `tar` in format 1); `checkout`, the end-of-line settings (`core.autocrlf`, `core.eol`) the files were checked out with, applied again on restore; when dirty `patch` and `untracked[]`; `submodules` (path to commit), each also captured as its own entry; `path` for a second repository or a submodule, relative to the first |
| `data[]` | `path` relative to the main repository, `sha256`, `size` |
| `environment` | `python` (version, implementation, executable, prefix, platform, machine), `lock` (pip freeze, with `packages` count), `wheels[]` (`file`, `sha256`, `size`), `unpinnable[]`, `conda`, `hardware` (cpu, cores, memory_kb, gpus) |
| `run` | `argv`, `cwd` (relative to the main repository), `env`, `seeds`, `observed` (false for `capture`), `started_at`, `duration_s`, `exit_code`, `stdout`, `stderr`, `metrics_path`, and on a replay `replay` (setup, pip overrides) |
| `outputs[]` | `path`, `sha256`, `size` |
| `metrics` | The metrics JSON as the run wrote it |
| `result` | `metric`, `value`, `target` |
| `tolerance` | `rtol`, `atol`: how close a replay's metrics must be |
| `retest_of`, `comparison` | On a retest: the capsule retested, and `verdict`, per-metric `was`, `now`, `delta`, `ok`, and outputs `identical`, `changed`, `new` |

## How the code is kept

A commit id names the code, but a repository can be rewritten, made private or lost, and a branch deleted before it merges takes its commits with it. Copying the whole tree into every capsule would protect against that, at the cost of storing the same files again for every commit. The vault lets git do what it is good at instead.

- Tag. The commit is tagged `vault/<first 12 digits>` in the repository, and the tag pushed to `origin`, so neither a deleted branch nor git's garbage collection can drop it.
- Bundle. The vault keeps each repository's history as git bundles under `repos/<root commit>/`, the root commit naming the repository wherever it is cloned. A capture lists the bundles already there and, when the vault does not yet hold the commit, writes one bundle of only the commits it lacks (`git bundle create ... --not <tips the vault holds>`). The first capsule of a repository stores its history once, at about git's own packed size; each later commit adds kilobytes. Bundles are named by their tip commit and never overwritten.
- Restore. The capsule lists the bundles that hold its commit. Restore initialises an empty repository, applies the bundles in the order their prerequisites allow, checks out the commit, and compares the checked-out tree with the recorded `tree`. Git checks every object's hash as it reads the bundles, so a match proves the code is the commit, bit for bit, with no need for the original repository or its remote.

A shallow clone has no history to bundle, so its capture falls back to `storage: archive`: a gzip-compressed tar of the commit (`git archive`), deterministic for a commit, with `exact: true` when the tar's own git tree hash equals the commit's. It is false when `.gitattributes` uses `export-ignore`, `export-subst` or end-of-line conversion; the commit is still recorded, and `show` flags it. `--code-storage archive` (or `vault.code_storage: archive`) asks for the snapshot on purpose, for a repository with no history you want to keep. Capsules of format 1 hold a plain tar, and still restore.
