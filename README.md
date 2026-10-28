# AI-Assisted Research (RMS)

[![Version: v4.2.0](https://img.shields.io/badge/Version-v4.2.0-purple.svg)](CHANGELOG.md)
[![Licence: CC BY 4.0](https://img.shields.io/badge/content-CC%20BY%204.0-blue.svg)](LICENSES/CC-BY-4.0.txt)
[![Licence: Apache-2.0](https://img.shields.io/badge/code-Apache--2.0-blue.svg)](LICENSES/Apache-2.0.txt)

Four Agent Skills for tracking the lineage of ideas through structured, metric-driven research, run by AI agents. Research lives in a hypothesis DAG where every node is a measurable claim tested against a target fixed before the result is known; every experiment is kept as a capsule (its exact code, data, environment, command and outputs) that any later agent can replay; the skills frame, run, audit, retest and record each experiment, handing the work itself to the `work` skill of [AI-Assisted Work](https://github.com/dermot-obrien/ai-assisted-work) (AAW). It is also called the Research Management System (RMS).

This repository is a bundle: [`bundle.json`](bundle.json) lists the four skills, `research`, `research-dag`, `experiment-vault` and `literature-discovery`, and each installs on its own. There is no installer of its own and no npm package. Up to 2.0.0, AAR was a framework installed with `aar install` through AAW's engine; that layout is tagged [`v2.0.0`](https://github.com/dermot-obrien/ai-assisted-research/tree/v2.0.0) for anyone who still installs it that way with AAW 4.0.0.

## Requirements

- Node 18 or newer and git, for AI-Assisted Work's installer, [`bin/skills.mjs`](https://github.com/dermot-obrien/ai-assisted-work/blob/main/bin/skills.mjs). The workspace must be a git repository.
- Python 3.10 or newer with PyYAML and requests, for the tools inside the skills: `pip install -r requirements.txt`.
- The `work` skill from AI-Assisted Work (3.0.0 or later), installed in the same workspace. The research flows that create or run work delegate to it. `research-dag`, `experiment-vault` and `literature-discovery` need nothing else.
- For a vault in Google Cloud Storage, the gcloud CLI, signed in with access to the bucket ([storage](skills/experiment-vault/references/storage.md)). A vault can also be a plain folder.
- Any agent that reads [Agent Skills](https://agentskills.io/specification): VS Code with GitHub Copilot, Cursor, Claude Code, Codex, Gemini CLI and others.

## Install

### With skills.mjs, once

From the root of the git repository that will hold the research, with clones of both repositories inside it (add `.ai-assisted-work/` and `.ai-assisted-research/` to its `.gitignore`):

```bash
git clone https://github.com/dermot-obrien/ai-assisted-work.git .ai-assisted-work
git clone https://github.com/dermot-obrien/ai-assisted-research.git .ai-assisted-research
node .ai-assisted-work/bin/skills.mjs install work
node .ai-assisted-work/bin/skills.mjs install --bundle .ai-assisted-research
python -m pip install -r .ai-assisted-research/requirements.txt
```

`install --bundle` copies all four skills to `.agents/skills/<name>/`; name one (`install research --bundle .ai-assisted-research`) to install only that. It records each skill's source and a hash in `.agents/skills.lock.json`. Installing `research` before `work` works too, with a note that `research` needs `work`, which is not installed. Do not edit the installed copies: `node .ai-assisted-work/bin/skills.mjs check` reports any that changed, and the next install replaces them.

The installer does not create `research.yaml` or the research folder. The `/research start` and `/research init` flows do that, copying [`skills/research/assets/research.yaml.example`](skills/research/assets/research.yaml.example) to the workspace root when there is none. To use the tools before running a flow, copy it yourself and `mkdir research`. To keep experiments in a vault, uncomment its `vault:` block; the bucket is created once by a person ([storage](skills/experiment-vault/references/storage.md)).

### With a declaration, every session

A workspace that installs the same skills every session declares them in a committed `.agents/skills.json`:

```json
{
  "sources": [
    { "bundle": "https://github.com/dermot-obrien/ai-assisted-research.git", "ref": "main" },
    { "bundle": "https://github.com/dermot-obrien/ai-assisted-work.git", "ref": "main", "skills": ["work"] }
  ]
}
```

Keep a copy of `skills.mjs` in the workspace (for example `scripts/skills.mjs`) and run `node scripts/skills.mjs sync` once to install and write `.agents/skills.lock.json`; commit the lock too. A session start then runs `node scripts/skills.mjs sync --locked --copy`, which installs exactly the locked commits as copies. `sync` also removes any skill it installed that the declaration no longer lists, such as the eleven `aar-*` skills that an earlier version of the bundle listed; folders that `aar install` left are not in the lock, so delete those by hand. AI-Assisted Work's [Installing the skills](https://github.com/dermot-obrien/ai-assisted-work/blob/main/DEPLOYMENT.md) covers mirrors, machines with no network, updates and removal.

### Where agents read skills

The installer writes to `.agents/skills/`, the widest-read project location. Claude Code reads only `.claude/skills/`, so the installer links `.claude/skills/<name>` at the same folder when `.claude/` exists in the workspace (`--copy` copies instead). Create it before installing if you use Claude Code.

| Directory | Read by |
|---|---|
| `.agents/skills/` in the project | VS Code with GitHub Copilot, Cursor, Codex, Gemini CLI and others |
| `.github/skills/` in the project | VS Code with GitHub Copilot, and the Copilot coding agent |
| `.cursor/skills/` in the project | Cursor |
| `.claude/skills/` in the project | Claude Code, and also VS Code with GitHub Copilot and Cursor |
| `~/.agents/skills/`, `~/.copilot/skills/`, `~/.cursor/skills/`, `~/.claude/skills/` | The same tools, for every project |

Install `research` per workspace: it reads that workspace's `research.yaml` and needs the `work` skill beside it. `literature-discovery` is the exception. It needs neither, so it can go in a user-level folder and serve every project. Copy `skills/literature-discovery/` there and run `pip install -r <that folder>/requirements.txt`, or, with GitHub CLI 2.90 or later:

```bash
gh skill install dermot-obrien/ai-assisted-research literature-discovery --scope user
```

### Check it worked

```bash
node .ai-assisted-work/bin/skills.mjs check
python .agents/skills/research/bin/check.py
```

The first prints a tick for each installed skill. The second needs a `research.yaml` (it fails with `research.yaml: not found` until a flow or you create one) and then prints `research: ok`, with warnings for files a new workspace has not created yet. In your agent, type `/` and look for `/research`.

## Quick start

After installing, with `research.yaml` in place and a root node H-000 in `research/hypothesis-dag.yaml` ([quick start, step 4](docs/quick-start.md#4-write-a-tiny-dag)), add a hypothesis and see it become ready:

```bash
python .agents/skills/research-dag/bin/dag_update.py --dag research/hypothesis-dag.yaml --action add --parent H-000 --hypothesis "Adding day-of-week features lifts accuracy by at least 0.03" --plain-tested "Whether knowing the day of the week helps predict better" --target 0.03
python .agents/skills/research-dag/bin/generate_node_index.py
```

Then ask your agent for `/research frame H-001`. The [quick start](docs/quick-start.md)
does this from an empty folder, with the root node, the dashboard, the adoption check and a
literature search, in PowerShell and bash, in about ten minutes.

## Documentation

| Page | For |
|---|---|
| [Quick start](docs/quick-start.md) | A first real result in ten minutes |
| [Concepts](docs/concepts.md) | The DAG, statuses, readiness, the three phases, audit, adoption, the store |
| [User guide](docs/user-guide.md) | The full research cycle, step by step |
| [Skills](docs/skills.md) | The four skills and each research flow: what, when, needs, leaves behind |
| [Commands](docs/commands.md) | Every script, subcommand and flag |
| [Configuration](docs/configuration.md) | `research.yaml`, environment variables, precedence, file formats |
| [Troubleshooting](docs/troubleshooting.md) | Error and warning messages, and what to do |
| [Documentation index](docs/README.md) | Everything else: principles, roles, design notes, examples |

## The skills

Four skills, split where one can be used without the others. `research` is the method, as flows over one hypothesis DAG. `research-dag` owns the DAG and the only tools that change it, so an agent without the method can still read and write the same DAG. `experiment-vault` keeps every experiment as a replayable capsule and replays it, with or without a DAG. `literature-discovery` searches the literature. `research` needs the other two, and the `work` skill of AI-Assisted Work; each of the other three works alone.

| Skill or flow | Does |
|---|---|
| `/research start` | Baselines the state of the art and designs the hypothesis DAG |
| `/research init` | Reconstructs the lineage of research that predates AAR |
| `/research lineage` | Adds or revises hypotheses |
| `/research progress` | Picks the next ready node and drives it |
| `/research frame` | Designs one node's experiment as an AAW work item, fixing what will be captured |
| `/research run` | Runs a framed experiment on its own branch, every measured run kept in the vault |
| `/research sync` | Records the result in the DAG, from its capsule, and hands the conclusion back |
| `/research audit` | Replays the capsule and checks the result is sound, in a clean room |
| `/research retest` | Replays a result under a library, data or code change and records whether it held |
| `/research reconcile` | Checks results are live in the running system |
| `/research housekeep` | Refreshes the node index, reference check, capsule coverage and dashboard |
| `research-dag` | The hypothesis DAG's tools, with the optional shared DAG store and the node schema |
| `experiment-vault` | Keeps, verifies, restores and replays experiment capsules in a bucket or a folder |
| `literature-discovery` | Searches the literature and baselines the state of the art |

### Reproducing a prior experiment

```bash
python .agents/skills/experiment-vault/bin/vault.py run --node H-001 --data data/ --outputs out/ \
  --metrics out/metrics.json --metric accuracy --seed numpy=7 -- python train.py --seed 7
python .agents/skills/experiment-vault/bin/vault.py replay H-001/<capsule id>
```

The first tags the commit and keeps it as git history (only the commits the vault lacks, checked against the commit's tree on restore), the data, the frozen environment, the command, seeds, console output and outputs, and appends the capsule to node H-001. The second, on any machine and at any later date, restores it into a fresh virtual environment, runs it again and says whether the result is identical, reproduced within the tolerance fixed at capture, or drifted. Old capsules move to archive storage on their own and stay readable at once. [The experiment-vault skill](skills/experiment-vault/SKILL.md) has the rest.

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
python -m unittest discover -s tests             # the DAG store and vault tests
```

On Windows, set `PYTHONUTF8=1` before running `skills-ref`, which otherwise reads
`SKILL.md` in the system code page.

## Licensing

This framework is permissively licensed to encourage the widest possible adoption: private, public, academic, and commercial. Attribution is the primary expectation.

- Documentation, agent specifications, skills, templates ([`CC BY 4.0`](LICENSES/CC-BY-4.0.txt)): use, share, modify, and redistribute, including commercially, with attribution.
- Executable code (the skills' `bin/` and `scripts/`, and the repository's `scripts/`) ([`Apache-2.0`](LICENSES/Apache-2.0.txt)): same permissions, with an explicit patent grant.

Per-file licensing is declared via SPDX identifiers and the [`REUSE.toml`](REUSE.toml) manifest, following the [REUSE Specification 3.3](https://reuse.software/spec-3.3/). See [`LICENSE`](LICENSE) for the full overview, including the trademark notice and attribution expectations.

---

*Created by [Dermot O'Brien](https://www.dermot-obrien.com/). Building frameworks for scaling human cognition through structured agentic workflows.*
