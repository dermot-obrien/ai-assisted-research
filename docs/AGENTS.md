# RMS Agent Protocols & Personalities

This document summarises the specialised roles in the Research Management System. Each role is
now a standalone [Agent Skill](https://agentskills.io) under [`skills/`](../skills/), carrying
its own protocol; this page is the overview of how they relate.

The `agents/` directory this page used to point at was retired when the per-tool command shims
were: a skill is self-contained, so the role definition and the command are one artefact rather
than two.

---

## 1. The Discovery Agent (The "Detective")

**Role**: Intellectual archaeologist and workspace investigator.

**Objective**: To discover the core initial hypothesis and subsequent refinements in an existing repository.

**Protocol**:
1.  **Fact-Based Discovery**: Scan the earliest commits, READMEs, and documentation for the "Kernel Idea."
2.  **Refinement Tracking**: Identify major architectural shifts representing refinements or branches.
3.  **Mandatory Provenance Check**: Cite specific evidence (commit hashes, PR numbers, file line numbers) for every discovery.
4.  **Verification Dialogue**: Present the discovered lineage to the user for confirmation.

**Full definition**: [`skills/aar-init-research/SKILL.md`](../skills/aar-init-research/SKILL.md), invoked as `/aar-init-research`

---

## 2. The Specialist (The "Strategist")

**Role**: Architect of the search space.

**Objective**: To baseline the SOTA and architect the research search space (Hypothesis DAG).

**Protocol**:
1.  **Gap Analysis**: Use academic APIs to identify the External Best Performance (EBP).
2.  **Hypothesis Formulation**: Formulate specific, measurable variants and avenues for exploration.
3.  **DAG Expansion**: Propose new nodes to the Hypothesis DAG.

**Full definition**: [`skills/aar-start-research/SKILL.md`](../skills/aar-start-research/SKILL.md), invoked as `/aar-start-research`

---

## 3. The Worker (The "Optimizer")

**Role**: Implementation engine and data generator.

**Objective**: To execute a research strand using the split Design/Execution workflow.

**Protocol**:
1.  **Design Phase**: Invoke `/start-hypothesis {node_id}` to create the blueprint (scope, research, and plan). Node moves to `framed`.
2.  **Execution Phase**: Invoke `/progress-hypothesis {WI_id} {node_id}` to create the Git research branch and execute implementation.
3.  **Homecoming Phase**: Invoke `/sync-research-result` to pull metrics and findings back to the DAG.

**Full definition**: [`skills/aar-progress-research/SKILL.md`](../skills/aar-progress-research/SKILL.md), invoked as `/aar-progress-research`

---

## 4. The Auditor (The "Validator")

**Role**: Scientific gatekeeper.

**Objective**: To rigorously verify research results and ensure scientific integrity.

**Protocol**:
1.  **Clean Room Verification**: Pull benchmark scripts from `main` branch, not the research branch.
2.  **Performance Verification**: Re-run benchmark suites using the clean environment.
3.  **Code Review**: Verify changes are non-destructive and artifact-free.
4.  **Consistency Check**: Confirm data, actual performance, and article claims are aligned.

**Full definition**: [`skills/aar-run-audit/SKILL.md`](../skills/aar-run-audit/SKILL.md), invoked as `/aar-run-audit`

---

## 5. The Reconciler (The "Drift Detector")

**Role**: Implementation-fidelity checker.

**Objective**: To determine whether the running system embodies what the research established, and to report the gap without proposing how to close it.

**Protocol**:
1.  **Two axes**: `status` says whether a hypothesis is true; `adoption.state` says whether it is live. Report on the second.
2.  **Demonstrate, do not assert**: a node claiming adoption without a `verification` predicate is unverified, not adopted.
3.  **Read the artefact, not the pointer**: confirm against source; a pointer that disagrees with the source is itself a finding.
4.  **Separate absence from contradiction**, and blocked from unexplained.
5.  **Report the gap, propose nothing**: remedies belong in a work item raised afterwards.

This is distinct from the Auditor. The Auditor asks whether the research is sound and stops at the boundary of the experiment. The Reconciler asks whether it reached production.

**Full definition**: [`skills/aar-reconcile/SKILL.md`](../skills/aar-reconcile/SKILL.md), invoked as `/aar-reconcile` · **Standard**: [`docs/adoption-and-drift.md`](adoption-and-drift.md)

---

## 6. The Housekeeper (The "Curator")

**Role**: Dashboard and visualization maintainer.

**Objective**: To maintain the project dashboard and provide clear visual access to the research lineage.

**Protocol**:
1.  Sync the Hypothesis DAG with the latest node statuses.
2.  Update the interactive Mermaid visual in the dashboard.
3.  Ensure all deliverables are correctly linked and accessible.

**Full definition**: [`skills/aar-housekeep/SKILL.md`](../skills/aar-housekeep/SKILL.md), invoked as `/aar-housekeep`
