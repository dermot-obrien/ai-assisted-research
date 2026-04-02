# Research Management System (RMS)

[![Version: v1.2.0](https://img.shields.io/badge/Version-v1.2.0-purple.svg)](CHANGELOG.md)
[![License: AGPL-3.0](https://img.shields.io/badge/License-AGPL%203.0-blue.svg)](https://www.gnu.org/licenses/agpl-3.0)
[![Commercial License Available](https://img.shields.io/badge/Commercial-License%20Available-green.svg)](LICENSE-COMMERCIAL.txt)
[![Docs License: CC BY 4.0](https://img.shields.io/badge/Docs-CC%20BY%204.0-lightgrey.svg)](https://creativecommons.org/licenses/by/4.0/)

A standalone, performance-driven agentic framework for tracking the **lineage of ideas** through structured research and discovery.

The Research Management System (RMS) enables multiple AI agents to collaboratively navigate a "Hypothesis Space" and conduct rigorous scientific research. It is designed to scale human discovery by providing the scaffolding that AI agents need to be truly autonomous.

---

## Prerequisites

This system is built for researchers and developers who are already using high-end AI agentic tools like **Anthropic Claude Code**, **Google Gemini CLI**, or **OpenAI Codex**.

### Mandatory Dependency: AI-Assisted Work (AAW)
The RMS uses the **AI-Assisted Work (AAW)** framework as its process management engine. **AAW is a mandatory prerequisite.**

- **AI-Assisted Work (AAW)**: [github.com/dermot-obrien/ai-assisted-work](https://github.com/dermot-obrien/ai-assisted-work)
- **Framework Sync**: Ensure you have the latest version of AAW installed as a peer or parent directory.

### Environment
- **Python 3.10+**: Required to run the tools in `tools/`.
- **Required Libraries**: `pip install pyyaml requests`
- **Git**: Required for lineage tracking and branching.

---

## Quick Start

### 1. Sub-module Installation
To include this system in your project, add it as a Git sub-module with the specific name **`.ai-assisted-research`**:

```bash
git submodule add https://github.com/dermot-obrien/ai-assisted-research .ai-assisted-research
```

*Note: Ensure `.ai-assisted-work` is also available in your repository.*

### 2. Skill Activation
This workspace provides pre-defined skills for different agent systems. Copy the relevant folder from `skills/` to your project's agent configuration directory (e.g., `.gemini/skills/rms/`).

### 3. Initialize Research
- **Existing Projects**: Use `/init-research` to reconstruct the lineage from your history.
- **New Projects**: Use `/start-research {topic}` to brainstorm the initial Hypothesis DAG.

### 4. Start a Session
```bash
/session-start
```
Shows the dashboard, lists the golden path (highest-priority nodes), and briefs you on recent breakthroughs and pending cascades.

### 5. Execute Research
Claim a hypothesis node, design the experiment, and execute:
```bash
/start-hypothesis {node_id}           # Design phase: scope and plan
/progress-hypothesis {WI_id} {node_id} # Execution phase: implement and run
```

### 6. Log Experiments (NEW in v1.2.0)
After each experiment, record the result in one step:
```bash
/log-experiment {node_id} metric=value "hypothesis description"
```
This updates the experiment log, DAG, node index, and dashboard automatically.

For breakthroughs (results that change research direction):
```bash
/log-experiment {node_id} metric=value "hypothesis" --breakthrough "Title"
```
This triggers automatic cascade analysis.

### 7. End a Session
```bash
/session-end
```
Generates a session report, commits it, and provides a handoff summary for the next session.

### 8. Close the Loop
```bash
/sync-research-result {node_id} {WI_id}
```

---

## Core Features

- **Hypothesis DAG**: Directed acyclic graph tracking the full research search space — what's been tried, what works, what's next.
- **Experiment Tracking** (v1.2.0): Experiments are first-class. `/log-experiment` records results and syncs to the DAG in one step.
- **Breakthrough Cascade** (v1.2.0): When a finding changes assumptions, `/cascade` propagates effects through the DAG automatically.
- **Session Continuity** (v1.2.0): `/session-start` briefing and `/session-end` handoff ensure no knowledge is lost between sessions.
- **Interactive Dashboard**: D3.js force-directed graph with breakthrough diamonds, golden paths, paper tracking, and findings graph.
- **Publication Tracking** (v1.2.0): Link DAG nodes to papers, track draft/submitted/published status.
- **Findings Graph** (v1.2.0): Adjacent directed graph showing how findings relate (contradicts, reinforces, unblocks).
- **Multi-Agent Ecosystem**: Specialized roles (Discovery, Specialist, Worker, Auditor, Housekeeper, Session, Cascade).
- **Metric-Driven Lineage**: Every hypothesis has quantifiable targets; every experiment records a metric.
- **Automated Synthesis**: Blog posts, arXiv drafts, and Research Changes from experiment findings.

---

## Documentation

- [**System Overview**](docs/README.md)
- [**User Guide**](docs/user-guide.md)
- [**Research Principles**](docs/PRINCIPLES.md): The core guardrails for autonomous research.
- [**Agent Definitions**](agents/): Detailed protocols for each specialized role.

---

## Licensing

The Research Management System is **dual-licensed**:
- **AGPL-3.0**: For open-source projects and non-commercial use.
- **Commercial License**: For proprietary, closed-source, or SaaS use.

Documentation is licensed under **CC BY 4.0**. See [LICENSE](LICENSE) for full details.

---

*Created by [Dermot O'Brien](https://www.dermot-obrien.com/). Building frameworks for scaling human cognition through structured agentic workflows.*
