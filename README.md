# Research Management System (RMS)

[![Version: v1.1.0](https://img.shields.io/badge/Version-v1.1.0-purple.svg)](CHANGELOG.md)
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

AAR installs through the shared AAW engine (it depends on AAW). Both models below work
**without npm-registry access**. The installer wires skill shims for every detected tool
(Claude/Cursor/Gemini), seeds a `research.yaml`, creates the `research/` data dir, and
`pip install`s AAR's Python deps.

### Option A — npm git-dependency (recommended)

Installing AAR auto-pulls AAW (declared as its dependency):

```bash
npm i github:dermot-obrien/ai-assisted-research
npx aar install            # add --no-python to skip pip
```

### Option B — git submodules

```bash
git submodule add https://github.com/dermot-obrien/ai-assisted-work .ai-assisted-work
git submodule add https://github.com/dermot-obrien/ai-assisted-research .ai-assisted-research
node .ai-assisted-research/bin/aar.js install       # add --no-python to skip pip
```

Either way replaces the old manual "copy the `skills/` folder" step. Re-run any time to
refresh shims; your `research.yaml` and `research/` data are left untouched.

> **Developers:** AAR's tooling is Python (`tools/*.py`) — there is nothing to build.
> The `aar` launcher is a zero-dependency Node script that delegates to AAW's engine
> (found via npm dependency, `node_modules`, or the `.ai-assisted-work` submodule).
> Runtime requirements: **Python 3.10+** and `pip install -r requirements.txt`
> (PyYAML, requests) — the installer runs this for you unless you pass `--no-python`.

### 3. Initialize Research
- **Existing Projects**: Use `/init-research` to reconstruct the lineage from your history.
- **New Projects**: Use `/start-research {topic}` to brainstorm the initial Hypothesis DAG.

### 4. Execute a Strand
Claim a hypothesis node and design the experiment:
```bash
/start-hypothesis {node_id}
```
This command creates a properly scoped AAW work item. Then, activate and implement:
```bash
/progress-hypothesis {WI_id} {node_id}
```
This activates the implementation branch and hands off to the work management agents for execution. Finally, close the loop:
```bash
/sync-research-result {node_id} {WI_id}
```

---

## Core Features

- **Metric-Driven Lineage**: Tracks the evolution of ideas through quantifiable performance gains against State-of-the-Art (SOTA) baselines.
- **Multi-Agent Ecosystem**: Specialized roles (Discovery, Specialist, Worker, Auditor, Housekeeper) working together.
- **Integrated Dashboards**: Interactive Mermaid and SVG visuals of the Hypothesis Graph.
- **Automated Synthesis**: Generates Blog posts, arXiv drafts, and Research Changes logs directly from experiment findings.

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
