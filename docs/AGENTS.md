# RMS Agent Protocols & Personalities

This document provides a summary of the specialized roles in the Research Management System. For full protocols, see the individual [agent definitions](../agents/).

---

## 1. The Discovery Agent (The "Detective")

**Role**: Intellectual archaeologist and workspace investigator.

**Objective**: To discover the core initial hypothesis and subsequent refinements in an existing repository.

**Protocol**:
1.  **Fact-Based Discovery**: Scan the earliest commits, READMEs, and documentation for the "Kernel Idea."
2.  **Refinement Tracking**: Identify major architectural shifts representing refinements or branches.
3.  **Mandatory Provenance Check**: Cite specific evidence (commit hashes, PR numbers, file line numbers) for every discovery.
4.  **Verification Dialogue**: Present the discovered lineage to the user for confirmation.

**Full Definition**: [`agents/discovery.md`](../agents/discovery.md)

---

## 2. The Specialist (The "Strategist")

**Role**: Architect of the search space.

**Objective**: To baseline the SOTA and architect the research search space (Hypothesis DAG).

**Protocol**:
1.  **Gap Analysis**: Use academic APIs to identify the External Best Performance (EBP).
2.  **Hypothesis Formulation**: Formulate specific, measurable variants and avenues for exploration.
3.  **DAG Expansion**: Propose new nodes to the Hypothesis DAG.

**Full Definition**: [`agents/specialist.md`](../agents/specialist.md)

---

## 3. The Worker (The "Optimizer")

**Role**: Implementation engine and data generator.

**Objective**: To execute a research strand using the split Design/Execution workflow.

**Protocol**:
1.  **Design Phase**: Invoke `/start-hypothesis {node_id}` to create the blueprint (scope, research, and plan). Node moves to `framed`.
2.  **Execution Phase**: Invoke `/progress-hypothesis {WI_id} {node_id}` to create the Git research branch and execute implementation.
3.  **Homecoming Phase**: Invoke `/sync-research-result` to pull metrics and findings back to the DAG.

**Full Definition**: [`agents/worker.md`](../agents/worker.md)

---

## 4. The Auditor (The "Validator")

**Role**: Scientific gatekeeper.

**Objective**: To rigorously verify research results and ensure scientific integrity.

**Protocol**:
1.  **Clean Room Verification**: Pull benchmark scripts from `main` branch, not the research branch.
2.  **Performance Verification**: Re-run benchmark suites using the clean environment.
3.  **Code Review**: Verify changes are non-destructive and artifact-free.
4.  **Consistency Check**: Confirm data, actual performance, and article claims are aligned.

**Full Definition**: [`agents/auditor.md`](../agents/auditor.md)

---

## 5. The Housekeeper (The "Curator")

**Role**: Dashboard and visualization maintainer.

**Objective**: To maintain the project dashboard and provide clear visual access to the research lineage.

**Protocol**:
1.  Sync the Hypothesis DAG with the latest node statuses.
2.  Update the interactive Mermaid visual in the dashboard.
3.  Ensure all deliverables are correctly linked and accessible.

**Full Definition**: [`agents/housekeeper.md`](../agents/housekeeper.md)
