# Changelog

All notable changes to the Research Management System (RMS).

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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

### Changed

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
