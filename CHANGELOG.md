# Changelog

All notable changes to the Research Management System (RMS).

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## 4.7.0

### Added
- `experiment-vault` 1.5.0: volatile outputs ([replaying](skills/experiment-vault/references/replaying.md), G44).
  - Outputs that differ on every run without the result differing, such as wall-clock timings, can be declared volatile: in `research.yaml` (`vault: volatile: keys: [...]` and `outputs: [...]`), with `--volatile-key` and `--volatile-output` on `run`, or on `replay` for an older capsule.
  - A replay leaves them out of its comparison and lists them apart, so a run that repeats its result exactly is `identical` instead of `drifted`. A JSON output that differs only in volatile keys counts as unchanged, and any other change still decides the verdict.
  - The capsule records the declaration, and every later replay uses it.
- `research` 4.4.1: a campaign replay where only timings moved is `reproduced`, and the pool reference says how to declare them.
- `research-dag` 2.3.1: its example `research.yaml` shows `vault.volatile` too.

## 4.6.0

### Added
- `research-dag` 2.3.0: every node carries four derived fields, written by the tools and never by hand ([node schema](skills/research-dag/references/node-schema.md)).
  - `created_at` and `last_activity_at`. In a DAG store they come from the node's events; in a plain file `dag_update.py` stamps them on each change.
  - `repeatability` says whether the result can be made again: `not_captured`, `captured`, `repeated`, `differs`, `broken` or `unverifiable`. It is read from the capsules and retest verdicts, newest first, and `repeated_at` says when the result last repeated. This separates results that have a repeatable test from those that do not.
  - In a store the derived fields never become events, so they cannot conflict. `dag_update.py --action set` refuses them, and `verify` and the round trip compare DAGs without them.
- `research` 4.4.0: a retest campaign can be narrowed to the paths from the root to some nodes, with `pool: campaigns: RT1: path_to: [...]` in `research.yaml`. Only those nodes and their ancestors are offered and counted, and an unknown node in `path_to` stops the campaign. `pool.py review` gives each node `repeatability` (state, when, capsule), `created_at`, `last_activity_at` and, in a narrowed campaign, `in_campaign`.

## 4.5.0

### Added
- `research` 4.3.0: `pool.py review` gives each node's `details`: its title, result, evidence and refutation as text, its newest five notes, work item, branch, code, datasets, adoption, whether it is contested, and its audit findings, long fields cut. It is what a person reads on clicking a hypothesis in mission control's graph, as the research dashboard shows it.

## 4.4.0

### Added
- `experiment-vault` 1.4.0: runtimes, so the same experiment gives the same result on any machine or agent platform. See [runtimes](skills/experiment-vault/references/runtimes.md) and protocol section 7.
  - `vault.py runtime create` writes a runtime once: the machine type, the exact Python build, the project's `uv.lock`, a determinism profile and a tolerance (0 by default). `runtime check` says whether a machine matches, and `runtime show` what a runtime holds.
  - A node fixes its runtime (`runtime` on the node). An evidence run of it is refused when the machine type or Python build differs, or the environment has drifted from `uv.lock` (`uv sync --frozen --check`), and it is refused before any holdout is claimed. An exploratory run is kept, with what differed.
  - The `cpu-deterministic-v1` profile is applied by the vault over whatever the caller set, and recorded for the replay. It sets one thread for every numeric library, a fixed OpenBLAS and MKL code path, AVX-512 off in the form the run's numpy accepts, deterministic GPU settings, the hash seed, the time zone and the locale.
  - A replay of a capsule with a runtime rebuilds the locked environment in the runtime's Python (`--setup uv`). `vault.py parity` passes only for an identical replay on another machine or platform that matched the runtime.
  - Regression testing by upgrade: `vault.py replay <capsule> --upgrade <checkout> --runtime <new runtime>` runs the capsule's pinned code with a newer `pyproject.toml` and `uv.lock`. A changed result is reported as drift and marked `upgrade`, and never counts as parity.
  - Every capsule records where it ran (`environment.machine`): the agent platform (`--tool`, `VAULT_AGENT_TOOL`, or detected), the OS, the architecture, the kernel, the C library, the CPU and its features, and the Python build. The node's capsule entry carries the platform, OS, architecture, CPU, Python and whether the runtime matched.
- `research` 4.2.0: the hypothesis pool and retest campaigns, run through the thread skill's board ([pool](skills/research/references/pool.md)).
  - `scripts/pool.py offer` posts every node whose parents are resolved as an open call. A node with `runner: local-gpu` goes only to the session holding `runner:local-gpu`.
  - `check` refuses work in the chain of a held node, so a held node locks its whole chain. `status` shows what is held, offered and waiting, and on what.
  - A campaign (`--campaign RT1`) retests every result from the root down, each node within a time box, and records `reproduced`, `rebuilt`, `differs` (the node becomes contested) or `unverifiable`.
  - An unverifiable node changes no result and never blocks its children. `revisit` lists the unverifiable nodes, the most depended on first.
  - Framing fixes a runtime. Sync waits for parity, and lineage changes check the chain is not held.
  - Upgrade campaigns (`offer --campaign UP1 --upgrade-to <runtime> --upgrade-branch <branch>`) regression-test every result with newer packages, recording `unchanged`, `changed`, `broken` or `unverifiable`. A changed result is a finding for a person, never a contested node.
  - `review [--json]` gives one domain-free snapshot of every hypothesis: a summary, what waits on a person, and each node's result, evidence, where it ran and pool state. Its contract is `skills/research/schemas/review.schema.json` (`research-review/1`), which mission control's Hypotheses view reads.
- `research-dag` 2.2.0: the node fields `runtime`, `runner` and `retests`.
- [Pool playbook](docs/pool-playbook.md): setting up Claude Code, Cursor, Codex, the other platforms and a GPU runner on your PC, running the pool and a campaign, and keeping it in proportion. Also an [architecture diagram](docs/architecture.svg).
- Guarantees G33 to G43, with their tests (`tests/test_runtimes.py`, `tests/test_pool.py`). Each of G34 to G43 was checked by breaking the code on purpose.

### Fixed
- The vault's git calls run with automatic gc and maintenance off. From git 2.56, a fetch or commit may start them in the background, still writing into a temporary repository the vault is deleting, which failed `verify --deep` with "Directory not empty".
- The DAG store's event times are strictly increasing within a process. On a coarse clock (Windows), two batches written one after the other could get the same time and replay in random order.

## 4.3.0

### Added
- `experiment-vault` 1.3.0 registers datasets once and lets capsules point at them. [Datasets](skills/experiment-vault/references/datasets.md) has the detail.
  - Versions and rules: `vault.py dataset create` registers a dataset with its sources, licence, owner and a rule. `dataset add` writes numbered versions (`v0001`, ...), each listing every file's hash and size, what changed since the version before, and where the data came from. Files are stored once as blobs, so a version that extends one file stores only that file again.
  - What the rules allow: an `append-only` dataset takes new files and files extended at their end; a `revisable` one takes changes as revisions, with a reason; a `frozen` one takes a single version. Only a person, at a terminal and with `CI` unset, revises an append-only dataset, and a revision lists every result built on an earlier version (`dataset impact`), to be retested.
  - Windows: `dataset window` defines named windows: a `backtest` span of history, a sealed `holdout` span, and a `forward` window of everything an append-only dataset gains after a version. No backtest window may overlap a holdout.
  - Runs: `run --dataset <name>@<version>:<mount>[:<window>]` fetches the version, hash-checked, into a read-only local cache. It links the version into a git-ignored folder and tells the run its version, folder, window and, for a forward window, the byte in each file where the new data starts (`VAULT_DATASETS`). The capsule records the version and window instead of copying the files. Restore, replay and verify use that version and refuse one whose record changed. A run that writes into its dataset is not recorded.
  - Sealed holdouts: each node gets one look at a sealed holdout, and a sibling of a node that looked gets none. The look is claimed before the run, and the node must be in the DAG. A dataset with a holdout is read only through a named window. Only a person may override a spent look, and the override is recorded.
  - Evidence classes: every capsule records its evidence class (`exploratory`, `untracked`, `backtest`, `holdout` or `forward`), on the capsule and on the node, and one test has one class.
- `research-dag` 2.1.0 adds the statuses `backtested`, `holdout_passed`, `forward_testing` and `retired`. The [node schema](skills/research-dag/references/node-schema.md) says which evidence class can move a node to which status. A passed holdout, forward testing and retirement resolve a parent for readiness, and backtesting keeps a node active.
- `research` 4.1.0: framing fixes a node's datasets, windows and decision rule. Running develops on the backtest window and looks at the holdout once. Sync sets the status by the capsule's evidence class, and retest finds the results a dataset revision touches.
- Guarantees G24 to G32, with the tests behind them (`tests/test_datasets.py`), each of G24 to G31 checked by breaking the code on purpose.

## 4.2.0

### Added
- `experiment-vault` 1.2.0: cloud sessions reach a `gs://` vault with a service account key in the environment variable `RESEARCH_VAULT_GCP_KEY` (the key file's JSON on one line, or the file in base64, since environment variables take one line), or a key file named by `RESEARCH_VAULT_GCP_KEY_FILE`. A session's setup script cannot read saved variables, so `vault.py` reads the key itself. It writes the key to a private temporary file, deleted when the command ends, and points only its own gcloud calls at it (`CLOUDSDK_AUTH_CREDENTIAL_FILE_OVERRIDE`). The machine's gcloud sign-in is left alone, the experiment runs without either variable, and the key is never printed or recorded. Its gcloud calls also run without `CLOUDSDK_AUTH_ACCESS_TOKEN`, which a cloud session presets as a placeholder for its proxy and which gcloud prefers to a key file: left in, every call was refused with `401 Invalid Credentials` (found by the first cloud-session test). A malformed key is named without showing it.

### Changed
- [Storage](skills/experiment-vault/references/storage.md) now gives the whole setup as it was run and checked:
  - a dedicated project, with a budget in the billing account's currency;
  - the bucket;
  - the agents' account, granted add and read on the bucket only;
  - initialising the vault;
  - a round trip, and proof that the account cannot delete or overwrite;
  - the key, including lifting the 2024 organisation key block for the one project and putting it back.

  It also covers the errors met on the way: billing quota, budget currency, the Application Default Credentials warning, and impersonation rights.

## 4.1.0

### Changed
- `experiment-vault` 1.1.0 keeps code as git history instead of a copy of the tree per capsule. `vault.py run` tags the commit `vault/<commit12>` and pushes the tag to `origin`, so a deleted branch or git's garbage collection cannot drop it (`--no-push-tag` keeps it local). The vault holds each repository's history as git bundles under `repos/<root commit>/<tip commit>.bundle`, each with only the commits the vault lacked. The first capsule of a repository stores its history once, at about git's own packed size, and each later commit adds kilobytes rather than the whole tree: on this repository, three commits took 3.7 MB as bundles against 9.6 MB as snapshots. Restore rebuilds the repository from the bundles, checks out the commit and checks its git tree, with no need for the original repository or its remote, and leaves a git checkout. `verify` checks the bundles are present, and `--deep` rebuilds the code.
- A shallow clone, or `--code-storage archive` (`vault.code_storage`), keeps a snapshot of the commit as before, now gzip-compressed and byte-identical for the same commit.
- Every submodule is captured as its own repository, and restored in place; a submodule that is not checked out stops the capture, since its code would be missing.
- The end-of-line settings the files were checked out with (`core.autocrlf`, `core.eol`) are recorded and applied on restore, so a run made on Windows restores with the bytes it read, whatever the restoring machine's settings.
- `run` keeps as outputs only the files the run wrote, and warns about any older file in an output folder.
- `run --dry-run` (and `capture --dry-run`) checks everything a capture needs and prints the plan, changing nothing.
- [Protocol](skills/experiment-vault/references/protocol.md): the procedure every agent follows, in MUST and MUST NOT steps, with the report format and what to do for each error. [Guarantees](skills/experiment-vault/references/guarantees.md): what the vault promises, each with the tests that prove it; a test fails when a named test does not exist.
- The unit tests run on Linux, Windows and macOS in CI, and check every manifest they read against the schema.
- Manifests are `experiment-vault/2`. Format 1 capsules, with their plain tar, still verify, restore and replay, and a newer format is refused with a message rather than misread.

## 4.0.0

### Added
- `experiment-vault` 1.0.0, a new skill: every hypothesis experiment kept as a self-contained, immutable capsule in a Google Cloud Storage bucket (through the gcloud CLI) or a folder, so any later agent can replay it. `vault.py run` runs the command and keeps the exact code (a tar of each repository at its commit, with `exact: true` when the tar's own git tree hash equals the commit's), the data it read, the interpreter, `pip freeze` and optionally every wheel (`--vendor-wheels`), the hardware, the command, seeds and result-changing environment variables, stdout and stderr, the outputs and the metrics. Files are stored once by SHA-256; the manifest is written last, never overwritten, and its id carries its hash. `capture` records a run that already happened; `list`, `show`, `verify` (`--sha256`, `--deep`), `restore` (with `replay.sh` and `replay.ps1`), `replay` (a fresh virtual environment from the lock or the vendored wheels, or `--setup none`, with `--pip` overrides; verdict `identical`, `reproduced`, `drifted` or `failed`, kept as a `retest` capsule), `run --retest-of`, `coverage` (result nodes with no capsule) and `lifecycle` (GCS storage class rules). Capsules are appended to the node's `capsules` field. [Storage](skills/experiment-vault/references/storage.md) covers the bucket: Autoclass with Archive as the terminal class, so old capsules get cheap and stay readable at once, and agents with create and read access only.
- `research` 4.0.0: the `/research retest` flow replays a node's capsule after a library, data or code change, notes the verdict, and moves a drifted `validated` or `ineffective` node to `contested`. `/research frame` fixes the command, inputs, outputs, seeds and replay tolerance before the run; `/research run` keeps every measured run in the vault; `/research sync` records a result only from a capsule on the node; `/research audit` replays the capsule first; `/research housekeep` runs `vault.py coverage --verify`. Each applies when `vault` is set in `research.yaml`.
- `research-dag` 2.0.0: `dag_update.py --action append` adds one item to a list field, written in a DAG store as an append event so concurrent appends survive. [Node schema](skills/research-dag/references/node-schema.md) sets out the fields, the status vocabulary and the `capsules` field.

### Changed (breaking)
- The DAG tools are a skill of their own again, `research-dag` 2.0.0, so an agent or another bundle can use the DAG without the research method: `dag_update.py`, `dag_store.py`, `generate_node_index.py`, `generate_dashboard.py`, `validate_dag_references.py`, `branch_manager.py` and `rms_config.py` move from `skills/research/bin/` to `skills/research-dag/bin/`, with `references/dag.md` (now `tools.md`), `dag-store.md`, the event schema and the DAG tools' argument schemas. `research` requires `research-dag` ^2.0.0 and `experiment-vault` ^1.0.0. Launchers at the old `research/bin/` paths run the new copies, with a note, until 5.0.0. Install the bundle again (`skills.mjs install --bundle`, or `sync` with the declaration) to get the new skills.

### Changed
- `literature-discovery` 1.1.4: the shared post-install check knows the new skills, and checks `experiment-vault` has git on PATH.
- `research.yaml.example` has a commented `vault:` block, and ships in `research-dag` too.

## 3.0.0

### Changed (breaking)
- AAR is no longer a framework installed through AI-Assisted Work's engine. The repository is a bundle: `bundle.json` lists two standalone Agent Skills, `research` and `literature-discovery`, and each installs on its own with AI-Assisted Work's `bin/skills.mjs` (`node <aaw>/bin/skills.mjs install --bundle <clone of this repository>`, or a committed `.agents/skills.json` declaration run with `skills.mjs sync --locked --copy`). The README has both.
- `aar install` is gone, with `bin/aar.js`, `framework.manifest.yaml` (its `depends: [aaw]` and `retired_skills`), the `.ai-assisted-work` submodule and `package.json`. There is no npm package and no `npx aar`. To keep installing with `aar install` through AI-Assisted Work 4.0.0, pin this repository at the `v2.0.0` tag, the last commit with the framework layout.
- No installer seeds `research.yaml` or creates `research/` any more, and none installs the Python packages: run `python -m pip install -r requirements.txt`. No installer removes the retired `aar-*` and `research-dag` skill folders either: `skills.mjs sync` removes skills it installed that the declaration no longer lists, and folders left by `aar install` are deleted by hand. The `research` skill still answers to the old names.
- The research principles and the inquiry seam are inside the `research` skill: `docs/PRINCIPLES.md` is now [`skills/research/references/principles.md`](skills/research/references/principles.md) and `docs/aaw-inquiry-seam.md` is [`skills/research/references/inquiry-seam.md`](skills/research/references/inquiry-seam.md), so an installed skill carries them.

### Changed
- `research` 3.1.0: the `/research start` and `/research init` flows create `research.yaml` from the skill's `assets/research.yaml.example`, and the folder its `dag_path` is in, when the workspace has none. The flows link the principles from their new place.
- `research` 3.1.0 and `literature-discovery` 1.1.3: when `research.yaml` is missing, the check says to run `/research start` or `/research init`, or copy the example, rather than an installer.
- Documentation describes installing with `skills.mjs`. The installer-only sections (the `aar` launcher in the command reference, `framework.manifest.yaml` in the configuration reference, the `aar install` messages in troubleshooting) are replaced by the `skills.mjs` commands and messages. Links from the documentation to each research flow point at its `references/<flow>.md`.

## 2.0.0

### Changed (breaking)
- The research skills are one skill, `research` 3.0.0 (WI-005 of AI-Assisted Work). `aar-start-research`,
  `aar-init-research`, `aar-update-lineage`, `aar-progress-research`, `aar-start-hypothesis`,
  `aar-progress-hypothesis`, `aar-sync-research-result`, `aar-run-audit`, `aar-reconcile`,
  `aar-housekeep` and their engine `research-dag` ran the same tools over the same files, so none
  worked installed alone. They are now flows of `research`: `/research start`, `init`, `lineage`,
  `progress`, `frame`, `run`, `sync`, `audit`, `reconcile`, `housekeep` and `dag`, each with its
  instructions in `references/<flow>.md`. The DAG tools are in `bin/`, the flows' own tools
  (`discovery.py`, `audit_verify.py`, `reconcile.py`) in `scripts/`, the templates in `assets/`.
  Nothing was dropped, and the skill's description still answers to the old names. The DAG store's
  folder (`~/.research-dags`), `RESEARCH_DAG_HOME` and its commit identity are unchanged, so existing
  stores keep working. `literature-discovery` stays a skill of its own; `/research start` uses it
  when it is installed. Migrate by installing `research` and removing the eleven old folders from
  `.agents/skills` and `.claude/skills`.

### Changed
- The research skills hand off to AI-Assisted Work's `work` skill: `/work start`,
  `/work progress` and `/work initiative`, which replaced `aaw-start-work`,
  `aaw-progress-work` and `aaw-start-initiative` in AI-Assisted Work 4.0.0. Their declared
  requirement is now `pkg:generic/dermot-obrien/ai-assisted-work/work ^3.0.0`, in each
  `SKILL.md` and in `bundle.json`. `aar-start-research`, `aar-start-hypothesis`,
  `aar-sync-research-result`, `aar-progress-research` and `aar-progress-hypothesis` move up a
  minor version; `aar-init-research`, whose wording alone changed, a patch.

### Added
- Troubleshooting covers the remaining messages the tools print: the DAG store's
  `NOT PUSHED`, unreadable-event and `verify` messages, the reference check's alias
  warning, `reconcile.py` without PyYAML, `sota_baseline.py` with no Semantic Scholar
  results, and `discovery.py` without a terminal.
- Documentation: a [quick start](docs/quick-start.md) run end to end on Windows in PowerShell
  and Git Bash, a [concepts](docs/concepts.md) guide, a guide to [each skill](docs/skills.md),
  a [command reference](docs/commands.md) checked against every tool's `--help`, a
  [configuration reference](docs/configuration.md) (`research.yaml`, environment variables,
  precedence, the files the tools read and write, the manifests) and
  [troubleshooting](docs/troubleshooting.md) keyed to the tools' messages. The README now
  covers installing for any agent, and `docs/README.md` is the index, with pointers to the
  examples in the repository. The user guide uses the `/aar-*` skill names and the installed
  tool paths.

### Fixed
- `aar-reconcile` 2.1.2: `reconcile.py --migrate` prints plain ASCII, so its summary no
  longer shows a garbled character in a Git Bash or other non-UTF-8 Windows console.
- `literature-discovery` 1.1.2: `sota_baseline.py` stamps `established_at` with a
  timezone-aware UTC time instead of the deprecated `datetime.utcnow()`, which warns on
  Python 3.12.
- `research-dag` 1.1.1:
  - `dag_update.py` without `--dag` edits `dag_path` from `research.yaml`, as the skill's
    examples assume, instead of `hypothesis-dag.yaml` in the working directory. With no
    `research.yaml` it still falls back to that file.
  - `dag_update.py --action add` refuses a parent that is not in the DAG. In a flat DAG it
    used to add the node with a dangling parent.
  - `dag_update.py` reports `DAG file not found` instead of a traceback when the DAG's
    folder does not exist, and reads and writes the DAG as UTF-8 on every platform.
  - `generate_node_index.py`, `generate_dashboard.py` and `validate_dag_references.py`
    answer `--help`. Before, `--help` needed a `research.yaml` and then ran the tool.
  - `branch_manager.py --action handoff` records the current time, not a fixed 2026-03-01
    timestamp, and no longer fails when `--instructions` is omitted.
  - The `research.yaml not found` message is plain ASCII, so it prints cleanly in a Windows
    console.
- `aar-init-research` 1.4.1: `scripts/discovery.py --help` prints usage instead of running
  the scan.
- `aar-reconcile` 2.1.1: `references/finding-kinds.md` lists `unknown_contester`, which
  `reconcile.py` reports.
- `aar --help` lists `--workspace` and `--yes`, and says where the launcher looks for AAW
  and that AAW must be installed first.
- **Every skill now passes `skills-ref validate`, the Agent Skills reference validator.** Five
  skills had an unquoted `description` containing ": ", which strict YAML parsers reject, so
  a client using one could not load them: `aar-housekeep`, `aar-progress-hypothesis`,
  `aar-start-hypothesis`, `aar-start-research` and `literature-discovery`. Every `description`
  is now quoted. No skill's behaviour changes. Versions: `aar-housekeep` and `aar-start-research` 2.1.1, `aar-progress-hypothesis` 1.4.1,
  `aar-start-hypothesis` 1.5.1, `literature-discovery` 1.1.1. The other skills' descriptions
  were quoted too, with the same parsed value, so their versions stay.

### Changed
- `aar-run-audit` 2.1.1: the body now points at its verifier, `scripts/audit_verify.py`, and
  says what it checks and how to run it. Before, only the `compatibility` field named it.
- README: an Agent Skills conformance section (the specification, where skills install, how to
  validate locally), and the install description now says skills go to `.agents/skills/<name>/`.

### Added
- **CI runs `skills-ref validate`** on every skill `bundle.json` lists, with `skills-ref`
  pinned to a commit of the agentskills repository, and fails if `bundle.json` and the
  `skills/` directories disagree. The zero-dependency `validate-skills.mjs` still runs for
  link checks; its lenient parser is why the YAML fault above went unnoticed.
- **`bundle.json`**, the bundle manifest DD-11 of AI-Assisted Work defines: each skill's version,
  purl, requirements (as each `x-skill-requires` states them) and post-install check. CI
  validates it with `scripts/validate-bundle.mjs`; the validator and the schema are copies from
  AI-Assisted Work in `scripts/vendor/`, so CI needs no network.
- **Post-install checks**, as DD-11 defines them: every skill ships the same `bin/check.py`
  (CI checks the copies agree), run from the workspace root with `SKILL_DIR` set. It checks
  Python 3.10 or newer, the packages the skill's own tools import (PyYAML for `research-dag`,
  `aar-housekeep`, `aar-reconcile` and `aar-run-audit`; PyYAML and requests for
  `literature-discovery`), and, for every skill but `literature-discovery`, `research.yaml`
  with `dag_path`, `node_index_path` and `work_items_path` set. A path not created yet is a
  warning; one whose folder does not exist is a problem. Exit 0 when all is well, 1 with one
  line per problem, 2 for a usage or environment error. CI runs every check in the scratch
  workspace, with `research.yaml` (they must pass) and without it (they must fail).
  Versions: `aar-housekeep`, `aar-reconcile`, `aar-run-audit` and `aar-start-research` 2.1.0;
  `aar-init-research`, `aar-progress-hypothesis`, `aar-progress-research` and
  `aar-update-lineage` 1.4.0; `aar-start-hypothesis` and `aar-sync-research-result` 1.5.0;
  `literature-discovery` 1.1.0; `research-dag` 1.1.0, released together with the DAG store below.

- `research-dag` 1.1.0: a shared, event-sourced store for the hypothesis DAG, so several machines
  and agents can change one DAG at once. Opt in with `dag_store` (a clone path, git URL or bare
  repository) and `dag_project` (the project's folder) in `research.yaml`; without them nothing
  changes. See `skills/research-dag/references/dag-store.md`.
  - The store is a separate git repository with one folder per project. Every change is a new,
    never-edited JSON event file, so writers never merge-conflict. `dag_update.py` pulls, writes
    events, and pushes with a retry on a rejected push.
  - `hypothesis-dag.yaml` becomes a view generated from the replay, with the source file's
    leading and per-node comments kept, so every tool that reads the YAML works unchanged.
  - Concurrent edits to one field: the later wins, and the replaced value is shown in the view,
    by `dag_update.py` and by `dag_store.py report`. Appends to a list all survive.
  - Concurrent adds under one id: the node already in the store keeps it, the other takes a
    letter suffix (H-204.4.25b) recorded as an alias event, and `validate_dag_references.py`
    reports aliases.
  - New `dag_store.py`: `import` seeds a project from an existing DAG, one event per node, and
    refuses unless replay reproduces it; `view`, `report`, `record` (turn direct edits of the
    view into events), `prune` (archive closed nodes' events; replay still reads them),
    `verify` and `sync`.
  - `dag_update.py` gains `relink`, `set` and `note` actions and `--no-store`, in both modes.
  - `dag_update.py` allocates hierarchical ids in a DAG that has them (the next child under
    the parent) instead of failing on them; a flat DAG keeps sequential numbering.
  - `schemas/dag_event.schema.json`, the updated `cli_schemas.json`, commented keys in
    `research.yaml.example`, unit tests under `tests/`, and a CI smoke test of the store
    against a local bare repository.

### Changed
- **The research skills are standalone, as DD-11 of AI-Assisted Work sets out.** No skill reaches
  into the framework clone any more (`.ai-assisted-research/tools/`, `templates/`); each carries
  what it runs, or requires the skill that does.
  - **`research-dag` 1.0.0, a new skill**: the hypothesis DAG engine the research skills share
    (`dag_update`, `generate_node_index`, `generate_dashboard`, `validate_dag_references`,
    `rms_config`, `branch_manager`, the CLI schemas, and the `research.yaml` template the
    installer seeds). The research skills require it by Package URL,
    `pkg:generic/dermot-obrien/ai-assisted-research/research-dag ^1.0.0`.
  - `reconcile.py` moved into `aar-reconcile/scripts/`, `audit_verify.py` into
    `aar-run-audit/scripts/`, `discovery.py` (workspace excavation) into
    `aar-init-research/scripts/`, and the report templates into
    `aar-progress-hypothesis/assets/templates/`.
  - **`literature-discovery` 1.0.0, a new skill**: literature search, `openalex_discovery`,
    `s2_ranking` and `sota_baseline`, with its own `requirements.txt`, usable on its own.
    `aar-start-research` requires it by Package URL,
    `pkg:generic/dermot-obrien/ai-assisted-research/literature-discovery ^1.0.0`.
  - Hand-offs to AI-Assisted Work are declared requirements: `aaw-start-work`,
    `aaw-progress-work` and `aaw-start-initiative`, by Package URL and range.
  - Versions: `aar-housekeep`, `aar-reconcile`, `aar-run-audit` and `aar-start-research` 2.0.0,
    because a documented command, a tool's location or a required skill changed;
    `aar-init-research`, `aar-progress-hypothesis`, `aar-progress-research` and
    `aar-update-lineage` 1.3.0; `aar-start-hypothesis` and `aar-sync-research-result` 1.4.0.
    `metadata.framework` is replaced by `metadata.homepage`, and the skills' `license` names the
    CC BY 4.0 and Apache-2.0 split.
  - The tools carry SPDX headers for Apache-2.0. Four still carried a stale GPLv3 line from
    before the relicensing to CC BY 4.0 and Apache-2.0.
  - The skills validator moved from `tools/` to `scripts/`, and CI runs the research-dag tools
    against a scratch workspace and checks the literature-discovery tools load.

### Added

- **Ten Agent Skills** under `skills/`, replacing the per-tool command shims:
  `/aar-start-research`, `/aar-init-research`, `/aar-start-hypothesis`,
  `/aar-progress-hypothesis`, `/aar-progress-research`, `/aar-sync-research-result`,
  `/aar-run-audit`, `/aar-reconcile`, `/aar-update-lineage`, `/aar-housekeep`. Each is a
  self-contained directory with a `SKILL.md` carrying a `description`, so an assistant can
  reach for one when a request matches rather than only when the command is typed. Bodies run
  38 to 96 lines against the spec's 500-line guidance.
- `skills` manifest key. `aar install` places the skills in `.agents/skills/<name>`, read
  natively by Codex, Cursor, GitHub Copilot, VS Code and Gemini CLI, and links
  `.claude/skills/<name>` at it for Claude Code, which reads only its own path. Requires
  **AAW 3.0.0 or later**.
- `tools/validate-skills.mjs`, a zero-dependency validator for the agentskills.io spec, and a
  CI workflow that runs it, installs into a scratch workspace, checks the Claude Code links
  resolve and that `research.yaml` is seeded, byte-compiles the Python tools and checks REUSE
  compliance. AAR had no CI before this.

### Removed

- **BREAKING: the per-tool command shims** under `skills/claude/commands/rms/`,
  `skills/cursor/` and `skills/gemini/`. A workspace that still invokes `/start-hypothesis`
  will find nothing behind it; use `/aar-start-hypothesis`. `aar install` sweeps away shims it
  previously wrote from `.claude/commands/aar`, `.cursor/rules/aar` and `.gemini/skills/aar`,
  since they point at files that no longer exist.
- **BREAKING: `agents/`.** The shims composed a command from one or two agent files; a skill
  needs no such composition, because the role and the command are one artefact.
  `docs/AGENTS.md` remains as the overview of how the roles relate, repointed at the skills.
- **BREAKING: the `shims` and `source_token` manifest keys.** Both existed only for the shims.

### Fixed

- `aar install` could not find AAW in the layout the README recommends. The launcher
  resolved AAW only as an npm dependency, in the workspace's `node_modules`, or as a clone
  inside the workspace, so one AAW clone serving several workspaces failed with "AAR requires
  AAW". It now also reads `modules.aaw.source_root` from the target workspace's
  `.aaw-config.yaml`, which `aaw install` writes for exactly this purpose. AAA's launcher
  already did this; AAR's had not kept up.
- `aar install --workspace PATH` ignored the flag and resolved the workspace from the current
  directory, so installing into anywhere other than the current tree silently targeted the
  wrong place.

### Changed

- **The skills enact the AAW inquiry seam** (aar-start-hypothesis and aar-sync-research-result
  1.3.0). The seam was documented but no skill carried it out. `/aar-start-hypothesis` now
  hands the experiment to `/aaw-start-work` as an intervention (or a change if local) and says
  it comes from AAR; AAW triage would otherwise read an uncertain hypothesis as an inquiry and
  route it back. `/aar-sync-research-result` gains Phase 5, which proposes the hand-back once
  the node is set: a delivery item for `validated`, a lesson for `ineffective`, a recorded
  close for `discarded`, and an AAA Decision Record where the finding settles an
  architectural choice. `docs/aaw-inquiry-seam.md` uses the `aar-` skill names, covers
  `discarded`, and points at AAW's current `docs/concepts/work-classification.md`.
- Content was preserved through the move rather than rewritten: the index-first node selection
  protocol is now a shared `references/node-selection.md` in the three skills that use it, and
  the Reconciler's finding-kind precedence is `references/finding-kinds.md`.
- `.gitignore` now ignores `.agents/skills/aar-*` and `aaw-*`: installed skills are generated
  from this repo, and tracking them in a consuming workspace invites drift.

### Added
- **AAW inquiry seam** (`docs/aaw-inquiry-seam.md`): defines the contract between RMS and the AI-Assisted Work work-classification standard — an AAW `inquiry` *is* an AAR hypothesis. Inbound: a triaged inquiry → `/start-hypothesis`. Outbound: a node conclusion **re-triages** into AAW delivery (`validated` → intervention/change; `ineffective` → close as a lesson; `contested`/`partially_tested` → keep researching). Aligns the vocabularies so one classification flows across both frameworks without drift.

### Changed
- **Relicensed for wide adoption.** Replaced the AGPL-3.0 + Commercial dual licence with a permissive split: **CC BY 4.0** for content (documentation, agent specifications, skills, templates) and **Apache-2.0** for executable code (`tools/*.py`, `bin/*.js`). Commercial use is now explicitly permitted under both licences; attribution is required. This brings RMS in line with the permissive licensing of AI-Assisted Work and AI-Assisted Architecture.
- Adopted [REUSE Specification 3.3](https://reuse.software/spec-3.3/) with `REUSE.toml` and `SPDX-License-Identifier` headers for per-file licensing metadata.
- Added a trademark notice for the "AI-Assisted Research" / "RMS" names; CC BY 4.0 and Apache-2.0 do not grant trademark rights.

### Removed
- `LICENSE-AGPL-3.0.txt` and `LICENSE-COMMERCIAL.txt` (superseded by `LICENSES/CC-BY-4.0.txt` and `LICENSES/Apache-2.0.txt`).

## [1.1.0] - 2026-03-01

### Added
- New `framed` status for hypothesis nodes to track experimental design separate from execution.
- `/start-hypothesis` command: Designs the scope and plan by delegating to AAW `/start-work`.
- `/progress-hypothesis` command: Activates implementation by delegating to AAW `/progress-work`.
- `/sync-research-result` command: Automated homecoming loop to pull findings/metrics back to the DAG.
- JSON schemas for CLI tools in `tools/schemas/cli_schemas.json` for agent interoperability.
- `templates/pivot_template.md` for structured reporting of ineffective hypotheses.
- `docs/articles/the-research-fog-and-ai-lineage.md`: Strategy guide for AI-assisted research.

### Changed
- Refactored monolithic strand execution into split design/execution flow (`/start-hypothesis` + `/progress-hypothesis`).
- Updated `tools/dag_update.py` with cross-platform concurrency locking (`DAGLock`).
- Hardened `agents/discovery.md` with mandatory provenance requirements.
- Hardened `agents/auditor.md` with "Clean Room" verification logic.
- Simplified execution hierarchy: all research now occurs within standard AAW `change/work-items/`.
- Updated `docs/PRINCIPLES.md` to reflect unified hierarchy and agent leeway.

### Removed
- Removed legacy strand execution commands (replaced by `/start-hypothesis` + `/progress-hypothesis`).

## [1.0.0] - 2026-03-01

### Added
- Initial public release
- Hypothesis DAG (Directed Acyclic Graph) for lineage tracking
- Multi-agent suite: Discovery, Specialist, Worker, Auditor, and Housekeeper
- Bridge to AI-Assisted Work (AAW) for process management
- Standardized performance benchmarks and datasets management
- Visualization templates for Blog, arXiv, and Research Changes
- Pre-defined skills for Gemini, Claude, and Cursor
