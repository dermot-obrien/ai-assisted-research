# Research Management System (RMS)

A standalone, performance-driven agentic system for tracking the **lineage of ideas** and conducting academic research.

---

## System Overview

The Research Management System (RMS) enables multiple AI agents to collaboratively navigate a "Hypothesis Space" and conduct rigorous scientific research. It is built on three core pillars:
1.  **Metric-Driven Lineage**: Tracking the evolution of ideas through actual performance gains against State-of-the-Art (SOTA) baselines.
2.  **Git-Centric Persistence**: Leveraging the natural versioning and branching of Git to maintain research strands.
3.  **Multi-Agent Ecosystem**: Specialized roles (Discovery, Specialist, Worker, Auditor) working together under Human-in-the-Loop (HITL) supervision.

---

## Visual Architecture

### 1. The Hypothesis Lineage Graph
The DAG tracks the branching and merging of research avenues.

```mermaid
graph TD
    H00[H-000: SOTA Baseline] --> H01[H-001: Hypothesis A]
    H00 --> H02[H-002: Hypothesis B]
    H01 --> H03[H-003: Hypothesis A.1]
    H02 --> H03
    H01 --> H04[H-004: Hypothesis A.2]
    
    style H00 fill:#f9f,stroke:#333,stroke-width:4px
    style H03 fill:#ccf,stroke:#f66,stroke-width:2px,stroke-dasharray: 5 5
```

### 2. Multi-Agent Workflow
How agents interact with the DAG and the repository.

```mermaid
sequenceDiagram
    participant H as Human (Reviewer)
    participant D as Discovery (Detective)
    participant S as Specialist (Strategist)
    participant W as Worker (Optimizer)
    participant A as Auditor (Validator)
    participant K as Housekeeper (Curator)
    participant G as Git (Main Branch)

    H->>D: /init-research
    D->>D: Scan repo history for Kernel Idea
    D->>G: Initialize hypothesis-dag.yaml
    D->>H: Present discovered lineage (Review Gate 1)
    H->>S: Define Objective
    S->>S: SOTA baseline & gap analysis
    S->>S: Propose New Nodes
    S->>H: Submit Proposal (Review Gate 2)
    H->>W: Approve Avenue
    W->>W: /start-hypothesis (Design Phase)
    W->>W: /progress-hypothesis (Execution Phase)
    W->>W: Benchmarking & Synthesis
    W->>A: Handoff to Auditor
    A->>A: Clean Room Verification
    A->>A: Verify Results & Code
    A->>H: Ready for Review (Review Gate 3)
    H->>G: Sync Result & Merge to Main
    K->>K: Update Dashboard & Visuals
```

---

## Key Components

| Component | Description |
| :--- | :--- |
| **`hypothesis-dag.yaml`** | The central map of the research solution space (root or `docs/`). |
| **`change/work-items/WI-NNN-research-*/`** | Dedicated AAW work item for each research node. |
| **`metadata.yaml`** | Per-node state tracking, stored within the research work item. |
| **`tools/`** | Agent-executable tools for discovery, branching, and auditing. |
| **`templates/`** | Markdown templates for Blog, ARXIV, and Pivot reports. |

---

## Documentation Index

- [**User Guide**](user-guide.md): Step-by-Step Instructions.
- [**Research Principles**](PRINCIPLES.md): Core guardrails and model leeway clauses.
- [**Agent Definitions**](../agents/): Detailed protocols for each specialized role.
- [**Framework Design**](../change/work-items/WI-001-research-management-system/deliverables/D01-framework-design.md): Detailed schema documentation.
