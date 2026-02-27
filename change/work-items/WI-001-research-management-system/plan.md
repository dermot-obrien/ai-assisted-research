# Work Item Plan: WI-001 Research Management System

**Work Type:** mixed

## Analysis Summary

### Problem Statement

Researchers often lose the "lineage of ideas" during long-term projects involving multiple agents and sessions. There is a need for a standalone, performance-driven system that tracks research progress through a metric space (Hypothesis DAG) and produces both narrative-style blogs and formal academic articles.

### Current State

The workspace currently lacks a structured way to manage long-term research strands. While `aaw` provides work item management, it does not support specialized academic discovery, performance-based branching, or multi-agent orchestration for scientific research.

### Proposed Approach

Implement a standalone, Git-centric research management system. This includes:
- A centralized **Hypothesis DAG** for tracking research avenues.
- A **multi-agent ecosystem** (Specialist, Worker, Auditor) for autonomous execution.
- **SOTA baselining** via academic APIs (OpenAlex/Semantic Scholar).
- **Performance-driven validation** (branch-per-node with metric checks).
- **Human-in-the-loop (HITL)** review stages for scoping, proposals, and synthesis.

## Activity Dependency Graph

```
WI-001-A1 (Framework Design) ──┬──> WI-001-A3 (Agent Orchestration) ──> WI-001-A5 (HITL & Validation)
                               │
WI-001-A2 (Academic API Int) ──┘

WI-001-A4 (Output Templates) ──> WI-001-A5
```

**Parallel Opportunities:**
- A1 and A2 can run in parallel (design vs. API integration).
- A4 (templates) can start early but is finalized after A1 and A2.
- A3 (orchestration) requires the core framework and API logic.
- A5 (validation) is the final integration phase.

## Activities

### Activity WI-001-A1: Framework Design & Schema

**Depends on:** None (can start immediately)

**Outcome:** Core DAG schema and Git-centric workflow defined.

**Deliverable Document:** [WI-001-D01](deliverables/D01-framework-design.md)

| Task ID | Task | Effort | Deliverable | Status |
|---------|------|--------|-------------|--------|
| WI-001-A1-T1 | Define Hypothesis DAG schema (`hypothesis-dag.yaml`) | Low | D01 | Pending |
| WI-001-A1-T2 | Define Work-Item metadata schema (`metadata.yaml`) | Low | D01 | Pending |
| WI-001-A1-T3 | Design Git branching and handoff conventions | Medium | D01 | Pending |

### Activity WI-001-A2: Academic API Integration

**Depends on:** None

**Outcome:** Tools for SOTA baselining (OpenAlex/Semantic Scholar) available to agents.

**Deliverable Document:** [WI-001-D02](deliverables/D02-api-integration.md)

| Task ID | Task | Effort | Deliverable | Status |
|---------|------|--------|-------------|--------|
| WI-001-A2-T1 | Implement OpenAlex discovery tool | Medium | D02 | Pending |
| WI-001-A2-T2 | Implement Semantic Scholar ranking tool | Medium | D02 | Pending |
| WI-001-A2-T3 | Create SOTA Baseline generator script | Medium | D02 | Pending |

### Activity WI-001-A3: Multi-Agent Orchestration

**Depends on:** WI-001-A1, WI-001-A2

**Outcome:** Autonomous pipeline for Specialist, Worker, and Auditor agents.

**Deliverable Document:** [WI-001-D03](deliverables/D03-agent-orchestration.md)

| Task ID | Task | Effort | Deliverable | Status |
|---------|------|--------|-------------|--------|
| WI-001-A3-T1 | Implement Specialist (Planner) agent logic | High | D03 | Pending |
| WI-001-A3-T2 | Implement Worker (Optimizer) agent logic | High | D03 | Pending |
| WI-001-A3-T3 | Implement Auditor (Validator) agent logic | Medium | D03 | Pending |

### Activity WI-001-A4: Output Templates (ARXIV & Blog)

**Depends on:** None

**Outcome:** Markdown templates for narrative and formal research outputs.

**Deliverable Document:** [WI-001-D04](deliverables/D04-output-templates.md)

| Task ID | Task | Effort | Deliverable | Status |
|---------|------|--------|-------------|--------|
| WI-001-A4-T1 | Create Blog-style narrative template | Low | D04 | Pending |
| WI-001-A4-T2 | Create ARXIV-style formal paper template | Low | D04 | Pending |

### Activity WI-001-A5: HITL System & Final Validation

**Depends on:** WI-001-A3, WI-001-A4

**Outcome:** Human-in-the-loop review stages and system-wide verification.

**Deliverable Document:** [WI-001-D05](deliverables/D05-validation.md)

| Task ID | Task | Effort | Deliverable | Status |
|---------|------|--------|-------------|--------|
| WI-001-A5-T1 | Define HITL Review Stage interface | Medium | D05 | Pending |
| WI-001-A5-T2 | Perform end-to-end research simulation | High | D05 | Pending |
| WI-001-A5-T3 | Final system verification and documentation | Medium | D05 | Pending |

### Activity WI-001-A6: User Documentation

**Depends on:** WI-001-A5

**Outcome:** Comprehensive user documentation with step-by-step instructions and visuals.

**Deliverable Document:** [WI-001-D06](deliverables/D06-user-documentation.md)

| Task ID | Task | Effort | Deliverable | Status |
|---------|------|--------|-------------|--------|
| WI-001-A6-T1 | Create system overview and visual architecture docs | Medium | D06 | Pending |
| WI-001-A6-T2 | Create step-by-step user guide and tutorials | Medium | D06 | Pending |
| WI-001-A6-T3 | Final review and documentation cleanup | Low | D06 | Pending |

## Risks and Mitigations

| Risk | Impact | Likelihood | Mitigation |
|------|--------|------------|------------|
| Multi-agent race conditions | High | Medium | Implement soft-locking via `metadata.yaml` and branch checks. |
| API Rate limits (Semantic Scholar) | Medium | Medium | Use OpenAlex as primary; cache results; handle 429s. |
| Performance metric drift | High | Low | Enforce strict benchmarking in the Auditor agent. |

## Verification Approach

**For Development:**
- [ ] Unit tests for DAG management and metadata logic.
- [ ] Integration tests for Academic Source API calls.
- [ ] Automated end-to-end simulation of a research strand.
- [ ] Code review for Auditor agent logic.

**For Architecture:**
- [ ] DAG schema reviewed and approved.
- [ ] Git branching strategy validated.
- [ ] HITL review points clearly defined and tested.

## Rollback / Recovery Plan

The system is Git-centric. Any failed research strand or corrupted state can be reverted using standard Git commands (`git revert`, `git checkout`). The `hypothesis-dag.yaml` will be versioned to ensure it can be restored to a known good state.

## Final Verification Checklist

- [ ] All acceptance criteria from scope.md met.
- [ ] Hypothesis DAG system is functional.
- [ ] Multi-agent ecosystem (Specialist/Worker/Auditor) is operational.
- [ ] SOTA discovery via APIs is integrated.
- [ ] Blog and ARXIV templates are available.
- [ ] HITL review process is documented and tested.
