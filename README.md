# Research Management System (RMS)

A standalone framework for tracking the **lineage of ideas** through performance-driven, agentic research.

## Prerequisites

This system relies on Python for its operation and [AI Assisted Work](https://github.com/dermot-obrien/ai-assisted-work) to manage activities and tasks.

- **AI Assisted Work**: Must be installed as a submodule in the workspace (`.ai-assisted-work/`). See [AI Assisted Work](https://github.com/dermot-obrien/ai-assisted-work).
- **Intent repository or change directory**: Work items and initiatives are stored in an intent repo (e.g., `.irregular-timeseries-intent/change/work-items/`) or a `change/` directory in the workspace. This location must exist for the RMS to create research work items.
- **Python 3.10+**: Required to run the tools in `tools/`.
- **Required Python Libraries**:
  ```bash
  pip install pyyaml requests matplotlib networkx pycairo cairosvg
  ```
  | Package | Purpose |
  |---------|---------|
  | `pyyaml` | Parse hypothesis-dag.yaml and research.yaml |
  | `requests` | SOTA discovery API calls (Semantic Scholar) |
  | `matplotlib` | Render radial DAG visualization (SVG) |
  | `networkx` | Graph data structure for DAG layout |
  | `pycairo` | Native Cairo rendering backend |
  | `cairosvg` | Convert SVG to PNG raster output |
- **Setup & Credentials**:
  - **Semantic Scholar API Key**: Required for the Specialist agent to perform SOTA discovery and ranking. Obtain a key from the [Semantic Scholar API Console](https://www.semanticscholar.org/product/api#api-key-form). Set it as an environment variable: `export S2_API_KEY='your_key_here'`.
- **Git**: Required for lineage tracking and branching.
- **Mermaid.js Support**: Recommended for viewing the supplementary Mermaid diagram (native in VS Code and GitHub).

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

Once the sub-module is installed and skills are activated, follow these steps to start your research:

1.  **Initialize**:
    - For new projects: `/start-research {topic}` — creates initiative, root work item, signpost
    - For existing projects: `/init-research` — scans workspace, creates initiative + root work item + signpost
2.  **Propose**:
    - Add research avenues: `/update-lineage` — adds nodes to the DAG (in root work item deliverables)
3.  **Execute**:
    - Claim a node and begin implementation: `/execute-strand {node_id}` — creates AAW work item per node
4.  **Visualize**:
    - Update the research dashboard: `/housekeep` — syncs DAG statuses, initiative membership, and regenerates visuals (SVG + PNG + Mermaid)

---

## Core Features

- **Performance-Driven Lineage**: Tracks research progress through a metric space.
- **AAW Integration**: Research work items live in the intent repo alongside all other work items. Each hypothesis node becomes an AAW work item grouped under a research initiative.
- **Multi-Agent Ecosystem**: Specialized Discovery, Specialist, Worker, Auditor, and Housekeeper roles.
- **Integrated Dashboards**: Interactive Mermaid and SVG visuals of the Hypothesis DAG.
- **Standardized Performance Hub**: Centralized data and benchmark management.

## Documentation

- [**System Overview**](docs/README.md)
- [**User Guide**](docs/user-guide.md)
- [**Framework Design**](change/work-items/WI-001-research-management-system/deliverables/D01-framework-design.md)
