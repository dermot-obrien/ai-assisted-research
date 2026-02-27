# WI-001 Research Management System

## Summary

A standalone system for tracking the lineage of ideas across academic and blog research, enabling consistent agent-driven exploration and synthesis.

## Intent

Develop a robust, standalone framework that allows multiple AI agents (Gemini, Claude, Cursor) to collaboratively conduct long-term research. The system focuses on maintaining a persistent "lineage of ideas" using a Directed Acyclic Graph (DAG) structure, enabling agents to baseline the "State of the Art" (SOTA), propose additive changes, and generate both ARXIV-style academic papers and blog-style research segments.

> **AI Agents**: See [`scope-ai.md`](scope-ai.md) for intent formation history, decision rationale, and agent-specific instructions.

## Acceptance Criteria

- [ ] A defined "start-research" command/workflow for scoping and SOTA baselining.
- [ ] A persistent knowledge graph (DAG) implemented via Markdown/YAML tracked by Git.
- [ ] Integration with academic sources (Semantic Scholar API) for SOTA discovery.
- [ ] Support for generating ARXIV-style and blog-style outputs.
- [ ] A non-destructive, additive change mechanism for research iterations.
- [ ] A lock-based handoff protocol for multi-agent collaboration.

## Scope

### In Scope

- Design of the standalone research management framework and its conventions.
- Implementation of the `start-research` command/workflow.
- Metadata schema (YAML) for tracking research lineage and agent handoffs.
- Integration logic for academic source APIs (Semantic Scholar/ARXIV).
- Templates for ARXIV and blog outputs.

### Out of Scope

- Modifying the existing `aaw` (AI-Assisted Work) skill (this is a standalone system).
- Developing a custom GUI for the knowledge graph (focus on CLI/Agent accessibility).
- Destructive edits to the research base (all changes must be additive).

## Context

### Related Documentation

- `.ai-assisted-work/skill-definitions/work-management/README.md` - Context on work item management conventions.

### Related Work Items

- None (Initial work item).

## Notes

- The system must remain platform-agnostic to work across different AI interfaces.
- Persistence is Git-centric to leverage existing versioning for lineage tracking.
