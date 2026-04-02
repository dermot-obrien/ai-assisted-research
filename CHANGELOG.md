# Changelog

All notable changes to the Research Management System (RMS).

Format based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).
Adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [Unreleased]

## [1.2.0] - 2026-04-02

### Added
- **Experiments as first-class concept**: `schemas/experiment.yaml` schema, `/log-experiment` command (`agents/log-experiment.md`). One-step experiment-to-DAG sync replacing 6 manual steps.
- **Breakthrough cascade mechanism**: `schemas/breakthroughs.yaml` schema, `/cascade` command (`agents/cascade.md`). When a breakthrough occurs, automatically identifies affected nodes and updates priorities.
- **Session continuity protocol**: `agents/session.md`, `/session-start` and `/session-end` commands. Briefing at start, report at end. Session reports stored in `sessions/` directory.
- **Publication tracking**: `schemas/publications.yaml` schema. Links DAG nodes to papers, tracks draft/submitted/published lifecycle.
- **Findings graph**: `schemas/findings-graph.yaml` schema. Adjacent directed graph tracking how findings relate (contradicts, reinforces, unblocks, strengthens, prompted, supersedes).
- **research.yaml schema**: `schemas/research-yaml.yaml` documenting all required and optional fields for the project signpost file.
- **New principles**: #8 Experiments are First-Class, #9 Breakthroughs Cascade, #10 Session Continuity.
- **New agent roles**: Log-Experiment, Cascade Analysis, Session Protocol.
- **New slash commands**: `/log-experiment`, `/cascade`, `/session-start`, `/session-end`.

### Changed
- Updated README to v1.2.0 with new Quick Start flow (session-first workflow).
- Updated PRINCIPLES.md with 3 new principles (8, 9, 10).
- Expanded Core Features in README to highlight experiment tracking, cascades, and session continuity.

### Motivation
Based on D09 framework evaluation (WI-037) after a 23-experiment research session that identified 8 framework gaps. The session demonstrated that experiments, breakthroughs, cascade effects, and session continuity are essential for productive research but were not supported by the framework.

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
