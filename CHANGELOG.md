# Changelog

All notable changes to the Research Management System (RMS).

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

### Added
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
