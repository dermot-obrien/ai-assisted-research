# AI-Assisted Research (RMS)

[![Version: v1.2.0](https://img.shields.io/badge/Version-v1.2.0-purple.svg)](CHANGELOG.md)
[![Licence: CC BY 4.0](https://img.shields.io/badge/content-CC%20BY%204.0-blue.svg)](LICENSES/CC-BY-4.0.txt)
[![Licence: Apache-2.0](https://img.shields.io/badge/code-Apache--2.0-blue.svg)](LICENSES/Apache-2.0.txt)

A framework for tracking the lineage of ideas through structured, metric-driven research,
run by AI agents. Research lives in a hypothesis DAG where every node is a measurable claim
tested against a target fixed before the result is known; twelve Agent Skills frame, run,
audit and record each experiment, handing the work itself to
[AI-Assisted Work](https://github.com/dermot-obrien/ai-assisted-work) (AAW). It is also
called the Research Management System (RMS).

## Requirements

- Node 18 or newer, for the installer.
- Python 3.10 or newer with PyYAML and requests, for the tools inside the skills. The
  installer runs `pip install -r requirements.txt` for you.
- git. The workspace must be a git repository.
- AI-Assisted Work, installed in the same workspace. The research skills that create or
  run work delegate to its `/aaw-*` skills, and its engine installs AAR.
- Any agent that reads [Agent Skills](https://agentskills.io/specification): VS Code with
  GitHub Copilot, Cursor, Claude Code, Codex, Gemini CLI and others.

## Install

### With the AAR installer (recommended, any agent)

From the root of the git repository that will hold the research:

```bash
npm i github:dermot-obrien/ai-assisted-research
npx aaw install --yes --work-items-path .aaw/work-items
npx aar install
```

`npm i` fetches AAR and AAW from GitHub; no npm registry access is needed. `aaw install`
sets up AAW and its skills; `aar install` then copies the twelve skills to
`.agents/skills/<name>/`, seeds `research.yaml`, creates `research/` and installs the
Python packages (`--no-python` skips that). Install AAW first: otherwise `aar install`
warns that its dependency is missing and exits 1.

Re-run `npx aar install` to update the skills; `research.yaml` and `research/` are left
alone. Do not edit the installed copies, since the next install replaces them.

Without npm, use clones (or submodules) inside the workspace:

```bash
git clone https://github.com/dermot-obrien/ai-assisted-work .ai-assisted-work
git clone https://github.com/dermot-obrien/ai-assisted-research .ai-assisted-research
node .ai-assisted-work/bin/aaw.js install --yes --work-items-path .aaw/work-items
node .ai-assisted-research/bin/aar.js install
```

### Where agents read skills

The installer writes to `.agents/skills/`, the widest-read project location. Claude Code
reads only `.claude/skills/`, so the installer links `.claude/skills/<name>` at the same
folder (a junction on Windows) when `.claude/` exists in the workspace. Create it before
installing if you use Claude Code.

| Directory | Read by |
|---|---|
| `.agents/skills/` in the project | VS Code with GitHub Copilot, Cursor, Codex, Gemini CLI and others |
| `.github/skills/` in the project | VS Code with GitHub Copilot, and the Copilot coding agent |
| `.cursor/skills/` in the project | Cursor |
| `.claude/skills/` in the project | Claude Code, and also VS Code with GitHub Copilot and Cursor |
| `~/.agents/skills/`, `~/.copilot/skills/`, `~/.cursor/skills/`, `~/.claude/skills/` | The same tools, for every project |

Install the research skills per workspace: they read that workspace's `research.yaml` and
need the AAW skills beside them. `literature-discovery` is the exception. It needs neither,
so it can go in a user-level folder and serve every project. Copy
`skills/literature-discovery/` there and run
`pip install -r <that folder>/requirements.txt`, or, with GitHub CLI 2.90 or later:

```bash
gh skill install dermot-obrien/ai-assisted-research literature-discovery --scope user
```

### Check it worked

```bash
python .agents/skills/research-dag/bin/check.py
```

It prints `research-dag: ok`, with warnings for files a new workspace has not created yet.
In your agent, type `/` and look for the `aar-*` skills.

## Quick start

After installing, and with a root node H-000 in `research/hypothesis-dag.yaml` ([quick start, step 4](docs/quick-start.md#4-write-a-tiny-dag)), add a hypothesis and see it become ready:

```bash
python .agents/skills/research-dag/bin/dag_update.py --dag research/hypothesis-dag.yaml --action add --parent H-000 --hypothesis "Adding day-of-week features lifts accuracy by at least 0.03" --target 0.03
python .agents/skills/research-dag/bin/generate_node_index.py
```

Then ask your agent for `/aar-start-hypothesis H-001`. The [quick start](docs/quick-start.md)
does this from an empty folder, with the root node, the dashboard, the adoption check and a
literature search, in PowerShell and bash, in about ten minutes.

## Documentation

| Page | For |
|---|---|
| [Quick start](docs/quick-start.md) | A first real result in ten minutes |
| [Concepts](docs/concepts.md) | The DAG, statuses, readiness, the three phases, audit, adoption, the store |
| [User guide](docs/user-guide.md) | The full research cycle, step by step |
| [Skills](docs/skills.md) | Each of the twelve skills: what, when, needs, leaves behind |
| [Commands](docs/commands.md) | Every script, subcommand and flag |
| [Configuration](docs/configuration.md) | `research.yaml`, environment variables, precedence, file formats |
| [Troubleshooting](docs/troubleshooting.md) | Error and warning messages, and what to do |
| [Documentation index](docs/README.md) | Everything else: principles, roles, design notes, examples |

## The skills

| Skill | Does |
|---|---|
| `aar-start-research` | Baselines the state of the art and designs the hypothesis DAG |
| `aar-init-research` | Reconstructs the lineage of research that predates AAR |
| `aar-update-lineage` | Adds or revises hypotheses |
| `aar-progress-research` | Picks the next ready node and drives it |
| `aar-start-hypothesis` | Designs one node's experiment as an AAW work item |
| `aar-progress-hypothesis` | Runs a framed experiment on its own branch |
| `aar-sync-research-result` | Records the result in the DAG and hands the conclusion back |
| `aar-run-audit` | Checks a result is sound, in a clean room |
| `aar-reconcile` | Checks results are live in the running system |
| `aar-housekeep` | Refreshes the node index, reference check and dashboard |
| `research-dag` | The DAG engine the others call, with the optional shared DAG store |
| `literature-discovery` | Searches the literature and baselines the state of the art; usable alone |

## Agent Skills conformance

Every skill in [`skills/`](skills/) follows the [Agent Skills specification](https://agentskills.io/specification):
a directory named after the skill, holding a `SKILL.md` whose YAML frontmatter has a `name`
that matches the directory and a `description` that says what the skill does and when to use
it. Metadata values are strings, bodies stay well under the 500-line guidance, and longer
material sits in the skill's `references/`, `scripts/` and `assets/` folders.
[`bundle.json`](bundle.json) lists the skills it ships.

CI validates every skill listed in `bundle.json` with `skills-ref`, the specification's
reference validator, and fails if `bundle.json` and the `skills/` directories disagree. To
validate locally (Python 3.11 or newer):

```bash
python -m venv .venv && . .venv/bin/activate    # on Windows: .venv\Scripts\activate
pip install "git+https://github.com/agentskills/agentskills#subdirectory=skills-ref"
for d in skills/*/; do skills-ref validate "$d"; done
node scripts/validate-skills.mjs skills          # also checks relative links resolve
node scripts/validate-bundle.mjs .               # bundle.json against the skills
python -m unittest discover -s tests             # the DAG store tests
```

On Windows, set `PYTHONUTF8=1` before running `skills-ref`, which otherwise reads
`SKILL.md` in the system code page.

## Licensing

This framework is permissively licensed to encourage the widest possible adoption: private, public, academic, and commercial. Attribution is the primary expectation.

- Documentation, agent specifications, skills, templates ([`CC BY 4.0`](LICENSES/CC-BY-4.0.txt)): use, share, modify, and redistribute, including commercially, with attribution.
- Executable code (the skills' `bin/` and `scripts/`, `bin/*.js`) ([`Apache-2.0`](LICENSES/Apache-2.0.txt)): same permissions, with an explicit patent grant.

Per-file licensing is declared via SPDX identifiers and the [`REUSE.toml`](REUSE.toml) manifest, following the [REUSE Specification 3.3](https://reuse.software/spec-3.3/). See [`LICENSE`](LICENSE) for the full overview, including the trademark notice and attribution expectations.

---

*Created by [Dermot O'Brien](https://www.dermot-obrien.com/). Building frameworks for scaling human cognition through structured agentic workflows.*
