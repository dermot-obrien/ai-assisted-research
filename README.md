# Research Management System (RMS)

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](CHANGELOG.md)
[![License](https://img.shields.io/badge/license-AGPL--3.0%20%2F%20Commercial-green.svg)](LICENSE)

A standalone, performance-driven agentic framework for tracking the **lineage of ideas** through structured research and discovery.

The Research Management System (RMS) enables multiple AI agents to collaboratively navigate a "Hypothesis Space" and conduct rigorous scientific research. It is designed to scale human discovery by providing the scaffolding that AI agents need to be truly autonomous.

---

## 🛠 Prerequisites

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

## 🚀 Quick Start

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

### 4. Execute a Strand
Claim a hypothesis node and begin the research process:
```bash
/research-hypothesis {node_id}
```
This command creates a properly scoped AAW work item and hands off to the work management agents for execution.

---

## 🧠 Core Features

- **Metric-Driven Lineage**: Tracks the evolution of ideas through quantifiable performance gains against State-of-the-Art (SOTA) baselines.
- **Multi-Agent Ecosystem**: Specialized roles (Discovery, Specialist, Worker, Auditor, Housekeeper) working together.
- **Integrated Dashboards**: Interactive Mermaid and SVG visuals of the Hypothesis Graph.
- **Automated Synthesis**: Generates Blog posts, arXiv drafts, and Research Changes logs directly from experiment findings.

---

## 📜 Documentation

- [**System Overview**](docs/README.md)
- [**User Guide**](docs/user-guide.md)
- [**Research Principles**](docs/PRINCIPLES.md): The core guardrails for autonomous research.
- [**Agent Definitions**](agents/): Detailed protocols for each specialized role.

---

## ⚖️ Licensing

The Research Management System is **dual-licensed**:
- **AGPL-3.0**: For open-source projects and non-commercial use.
- **Commercial License**: For proprietary, closed-source, or SaaS use.

Documentation is licensed under **CC BY 4.0**. See [LICENSE](LICENSE) for full details.

---

*Created by [Dermot O'Brien](https://www.dermot-obrien.com/). Building frameworks for scaling human cognition through structured agentic workflows.*
