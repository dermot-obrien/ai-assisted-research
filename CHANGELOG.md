# Changelog

All notable changes to the Research Management System (RMS).

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

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
