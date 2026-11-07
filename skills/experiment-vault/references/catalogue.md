# A dataset catalogue

Where an organisation keeps its datasets in a catalogue of its own (a data lake with versioned datasets, a data platform, a dataset registry), the vault reads versions from that catalogue instead of copying them, and tells the catalogue which capsules depend on each version so it keeps them. The catalogue keeps the data once; the vault keeps the evidence.

The vault's own datasets ([datasets](datasets.md)) still work beside a catalogue, and are the place for windows and sealed holdouts until the catalogue's versions have them.

## What a run records, and what a repeat reads

```bash
<vault.py> run --node H-12.3 --from-catalogue data/bars=bars@v0003 \
  --outputs out --metrics out/metrics.json --metric sharpe --dry-run -- python backtest.py
```

`--from-catalogue <mount>=<reference>` (repeatable) asks the catalogue to resolve the reference. An unpinned reference or `latest` resolves to the newest version at the start of the run. The vault then mounts the catalogue's folder for that version at `<mount>`, a git-ignored folder inside the repository. The run finds it in `VAULT_DATASETS`, as it finds a vault dataset.

The capsule records the catalogue's name, the dataset, the exact version, the digest (the sha256 of the version's manifest in the catalogue) and the mount, with the whole reference written as `name@vNNNN#sha256:<hex>`. It never records the files and never copies them.

A replay, restore or verify of the capsule resolves that exact reference, never `latest`. It refuses when the catalogue no longer has the version with that digest. A version's files are fixed when the catalogue writes it, so files added or replaced in later versions are not in the folder a repeat reads: it reads the original files and their original bytes, however the dataset has grown or been revised since.

## The catalogue keeps what capsules read

When the capsule is recorded, the vault asks the catalogue to pin each version for it, with the capsule's hash as the holder. A catalogue keeps a pinned version readable and does not remove it while the pin stands. If the catalogue cannot be reached at that moment, the capsule is still kept and the run fails with the command to finish the job: `vault.py pin <capsule>`, which is safe to run more than once.

## Only catalogue data, if you choose

`vault.inputs: catalogue` in `research.yaml` refuses `--data` unless the run says, with `--produced-data`, that those files were produced by the experiment itself (an earlier step's output, a fitted parameter file). Data from outside then has to be in the catalogue, read as a version. The capsule records `data_origin: produced` for those runs.

## Configuring a catalogue

```yaml
vault:
  uri: gs://example-research-vault/vault
  inputs: any                  # or: catalogue
  catalogue:
    name: lake                 # recorded in each capsule
    adapter: lake_client.vault:Catalogue
    python_path: []            # folders to add to the import path, relative to research.yaml
```

The adapter is a Python class the vault imports and builds with no arguments; it reads its own settings (credentials, endpoints) from the environment. It has four methods:

| Method | Returns | Must |
|---|---|---|
| `resolve(ref)` | `{"dataset": str, "version": "vNNNN", "digest": "sha256:<hex>"}` | Resolve an unpinned or `latest` reference to an exact version; refuse (raise) a reference whose `#sha256:` digest is not the version's, and a version that was removed |
| `materialize(ref)` | The path of a folder holding exactly the version's files, read-only | Check every file against the catalogue's checksums before returning, and put nothing else in the folder |
| `damage(ref, folder)` | A list of the files that are missing, added or of the wrong size | Be cheap: the vault calls it after every run, to catch a run that wrote into its data |
| `pin(ref, holder, reason, detail)` | Nothing | Record that the holder (a capsule's sha256) depends on the version; pinning the same holder twice changes nothing |

The test suite's folder catalogue (`tests/test_catalogue.py`) is a complete example in about fifty lines.
