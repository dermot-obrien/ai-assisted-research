# Decisions: WI-001 Research Management System

> Options considered and decisions made before planning.
> Created during the Discovery Phase (Plan Mode).

## Decision Summary

| ID | Decision | Chosen Option | Date |
|----|----------|---------------|------|
| D1 | System Architecture | Lightweight Git-Centric + Branching | 2026-02-28 |
| D2 | Lineage Structure | Directed Acyclic Graph (DAG) | 2026-02-28 |
| D3 | Search Methodology | Performance-Driven Metric Space Search | 2026-02-28 |
| D4 | Agent Ecosystem | Multi-Agent Orchestration (Specialist, Worker, Auditor) | 2026-02-28 |
| D5 | Academic Source Integration | Semantic Scholar API + OpenAlex | 2026-02-28 |

---

## D1: System Architecture

### Context

The system needs to support multiple agents across different sessions (Gemini, Claude, Cursor) while maintaining a consistent state and lineage.

### Options Considered

#### Option A: Lightweight Git-Centric + Branching

Focus on a file-based, Git-tracked system using Markdown/YAML. Agents interact via CLI and the local filesystem, using feature branches for research strands.

**Pros:**
- Platform-agnostic (works with any agent).
- Provides an immutable audit log via Git history.
- No complex infrastructure needed.
- Extremely "agent-friendly."

**Cons:**
- Requires robust branch management for parallel work.
- "Soft" locking relies on metadata conventions.

**Effort**: Medium

#### Option B: Graph Database + Web Service

Use a dedicated Graph Database (like Neo4j) and a central API to manage the research lineage and agent handoffs.

**Pros:**
- Richer querying for complex relationships.
- Better support for large-scale multi-user/agent collaboration.

**Cons:**
- High setup/maintenance overhead.
- Less "agent-friendly" (requires API integration).

**Effort**: High

### Decision

**Chosen**: Option A (Lightweight Git-Centric + Branching)

**Rationale**: Aligns with the requirement for a standalone system that works across multiple platforms and emphasizes the "lineage of ideas" through the natural versioning power of Git.

**Decided by**: User

**Date**: 2026-02-28

---

## D2: Lineage Structure

### Context

How to model the evolution of research ideas and hypotheses.

### Decision

**Chosen**: Directed Acyclic Graph (DAG)

**Rationale**: Allows for both branching (exploring variants) and merging (combining insights) without cycles, reflecting the reality of complex research lineages.

**Decided by**: User

**Date**: 2026-02-28

---

## D3: Search Methodology

### Context

The research needs to be rigorous and performance-oriented, not just exploratory.

### Decision

**Chosen**: Performance-Driven Metric Space Search

**Rationale**: Every research node must identify an "External Best Performance" (SOTA) and a benchmark/dataset. A path is only continued if it demonstrates better performance than its parent, turning research into a search for optimization in a metric space.

**Decided by**: User

**Date**: 2026-02-28

---

## D4: Agent Ecosystem

### Context

Transitioning from chat-style interactions to an autonomous research pipeline.

### Decision

**Chosen**: Multi-Agent Orchestration (Specialist, Worker, Auditor)

**Rationale**: Separate roles (Strategist, Specialist, Worker, Auditor) ensure specialized execution, rigorous validation, and human-in-the-loop review at key stages.

**Decided by**: User

**Date**: 2026-02-28

---

## D5: Academic Source Integration

### Context

How to baseline the "State of the Art" (SOTA) effectively.

### Decision

**Chosen**: Semantic Scholar API + OpenAlex

**Rationale**: OpenAlex provides massive breadth for discovery, while Semantic Scholar offers depth for ranking by "Influential Citations" and high-quality embeddings.

**Decided by**: User

**Date**: 2026-02-28

---

## Deferred Decisions

| Decision | Reason Deferred | Decide By |
|----------|-----------------|-----------|
| Orchestration Framework | Need to evaluate specific tools (e.g., LangGraph vs Custom) | Planning Phase |
| Benchmark Suite Integration | Depends on the specific repository's testing framework | Execution Phase |
