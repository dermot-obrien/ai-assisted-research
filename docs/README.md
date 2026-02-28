# Research Management System (RMS)

A standalone, performance-driven agentic system for tracking the **lineage of ideas** and conducting academic research.

---

## System Overview

The Research Management System (RMS) enables multiple AI agents to collaboratively navigate a "Hypothesis Space" and conduct rigorous scientific research. It is built on three core pillars:
1.  **Metric-Driven Lineage**: Tracking the evolution of ideas through actual performance gains against State-of-the-Art (SOTA) baselines.
2.  **Git-Centric Persistence**: Leveraging the natural versioning and branching of Git to maintain research strands.
3.  **Multi-Agent Ecosystem**: Specialized roles (Specialist, Worker, Auditor) working together under Human-in-the-Loop (HITL) supervision.

---

## Visual Architecture

### 1. The Hypothesis DAG (Directed Acyclic Graph)
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
    participant S as Specialist (Planner)
    participant W as Worker (Optimizer)
    participant A as Auditor (Validator)
    participant G as Git (Main Branch)

    H->>S: Define Objective
    S->>G: Initialize hypothesis-dag.yaml
    S->>S: Propose New Nodes
    S->>H: Submit Proposal (Review Gate 2)
    H->>W: Approve Avenue
    W->>W: Create Research Branch
    W->>W: Benchmarking & Synthesis
    W->>A: Handoff to Auditor
    A->>A: Verify Results & Code
    A->>H: Ready for Review (Review Gate 3)
    H->>G: Merge Research to Main
```

---

## Key Components

| Component | Description |
| :--- | :--- |
| **`research.yaml`** (workspace root) | Signpost for O(1) agent discovery — points to initiative, root work item, DAG, and work items directory. |
| **Initiative** (intent repo `change/initiatives/`) | AAW Initiative grouping all research work items under a strategic goal. |
| **Root Work Item** (intent repo `change/work-items/`) | Holds foundational artifacts: hypothesis-dag.yaml, RESEARCH_PLAN.md, SOTA documents. |
| **Per-node Work Items** (intent repo `change/work-items/`) | Individual AAW work items for each research strand, with deliverables (blog, arxiv, benchmarks). |
| **`tools/`** | Agent-executable tools for discovery, branching, auditing, and DAG visualization (`dag_visual.py` generates SVG + PNG). |
| **`templates/`** | Markdown templates for Blog, ARXIV output, and research.yaml signpost. |

---

## Documentation Index

- [**User Guide**](user-guide.md): Step-by-step instructions for humans and agents.
- [**Framework Design**](../change/work-items/WI-001-research-management-system/deliverables/D01-framework-design.md): Detailed schema and convention documentation.
- [**API Integration**](../change/work-items/WI-001-research-management-system/deliverables/D02-api-integration.md): Details on academic source integrations.
