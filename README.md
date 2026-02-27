# Research Management System (RMS)

A standalone framework for tracking the **lineage of ideas** through performance-driven, agentic research.

## Prerequisites

This system relies on Python and the **AI-Assisted Work (AAW)** system for its operation.

- **AI-Assisted Work (AAW)**: Mandatory sub-module for process management.
- **Python 3.10+**: Required to run the tools in `tools/`.
- **Required Libraries**:
  ```bash
  pip install pyyaml requests
  ```
- **Git**: Required for lineage tracking and branching.
- **Mermaid.js Support**: Recommended for viewing interactive dashboards (native in VS Code and GitHub).

---

## Sub-module Installation

To include this system in your project, add it as a Git sub-module with the specific name **`.ai-assisted-research`**:

```bash
git submodule add https://github.com/dermot-obrien/ai-assisted-research .ai-assisted-research
```

## Skill Activation

This workspace provides pre-defined skills for different agent systems. To enable them, copy the relevant folder from `skills/` to your project's top-level agent configuration directory.

### For Gemini:
Copy `skills/gemini/*` to `your-project/.gemini/skills/rms/`

### For Claude:
Copy `skills/claude/*` to `your-project/.claude/commands/rms/`

### For Cursor:
Copy `skills/cursor/*` to `your-project/.cursor/commands/rms/`

## Quick Start

Once the sub-module is installed and skills are activated, follow these 3 steps to start your research:

1.  **Initialize**: 
    - For new projects: `/start-research {topic}`
    - For existing projects: `/init-research`
2.  **Execute**:
    - Claim a node and begin implementation: `/execute-strand {node_id}`
3.  **Visualize**:
    - Update the research dashboard: `/housekeep`

---

## Core Features

- **Performance-Driven Lineage**: Tracks research progress through a metric space.
- **Multi-Agent Ecosystem**: Specialized Discovery, Specialist, Worker, Auditor, and Housekeeper roles.
- **Integrated Dashboards**: Interactive Mermaid and SVG visuals of the Hypothesis DAG.
- **Standardized Performance Hub**: Centralized data and benchmark management.

## Documentation

- [**System Overview**](docs/README.md)
- [**User Guide**](docs/user-guide.md)
- [**Framework Design**](change/work-items/WI-001-research-management-system/deliverables/D01-framework-design.md)
