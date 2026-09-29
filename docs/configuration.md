<!--
SPDX-FileCopyrightText: 2026 Dermot O'Brien
SPDX-License-Identifier: CC-BY-4.0
-->

# Configuration reference

Every setting AAR reads, where it is read from, and what wins when two sources disagree.

AAR's skills declare no `inputs.toml` binding keys. Their configuration is `research.yaml`
in the workspace, a few environment variables, and the command-line flags in the
[command reference](commands.md). The files the tools read and write (the DAG, the node
index, the dashboard inputs, `metadata.yaml`) are described after them, followed by the
repository's own manifests.

## research.yaml

One per workspace, at its root. The installer seeds it from
[`skills/research-dag/assets/research.yaml.example`](../skills/research-dag/assets/research.yaml.example)
if none exists, and never overwrites it. Read by every `research-dag` tool (through
`rms_config.py`), by the post-install checks, and by the skills.

String paths are relative to the folder that holds `research.yaml`.

| Key | Type | Default in the seeded file | Required | What it is |
|---|---|---|---|---|
| `dag_path` | path | `research/hypothesis-dag.yaml` | Yes | The hypothesis DAG. With a DAG store, the view generated from it |
| `node_index_path` | path | `research/node-index.yaml` | Yes | Where `generate_node_index.py` writes the index |
| `work_items_path` | path | `.aaw/work-items/` | Yes | Where AAW keeps work items for research nodes. Match `work_items_path` in `.aaw-config.yaml` |
| `dashboard.title` | string | `Research Hypothesis Dashboard` | No, that is also the tool's default | The dashboard's heading |
| `dashboard.experiments_dir` | path | `research/experiments` | For the dashboard and reference check | Folder of `*experiment-log.jsonl` files |
| `dashboard.breakthroughs` | path | `research/breakthroughs.yaml` | For the dashboard | Breakthroughs list |
| `dashboard.papers` | path | `research/papers.yaml` | For the dashboard | Papers tracked against nodes |
| `dashboard.findings_edges` | path | `research/findings-edges.yaml` | For the dashboard | Cross-node relationships |
| `dashboard.output_html` | path | `research/dashboard.html` | For the dashboard | Where the dashboard is written |
| `dag_store` | string | unset | No | A shared DAG store: a path to a clone, or a git URL or bare repository to clone |
| `dag_project` | string | unset | No | This project's folder in the store. A plain folder name |

A dashboard input file that does not exist is skipped; a missing `dashboard.*` key is an
error for the tools that need it. The dashboard inputs are optional files, so leave the
keys in place even when the files are not there yet.

`dag_store` and `dag_project` work as a pair. With both set, `dag_path` becomes a view
generated from the store and `dag_update.py` writes events to the store. With neither, the
DAG is the plain file. With only one, `dag_update.py` warns and edits the plain file.

A relative `dag_store` path resolves against the folder holding `research.yaml`. A URL or
a bare repository is cloned on first use into `$RESEARCH_DAG_HOME/<repository name>`.

Example with a store:

```yaml
dag_path: "research/hypothesis-dag.yaml"
node_index_path: "research/node-index.yaml"
work_items_path: ".aaw/work-items/"
dag_store: "https://example.com/you/research-dags.git"
dag_project: "my-project"
dashboard:
  title: "Churn research"
  experiments_dir: "research/experiments"
  breakthroughs: "research/breakthroughs.yaml"
  papers: "research/papers.yaml"
  findings_edges: "research/findings-edges.yaml"
  output_html: "research/dashboard.html"
```

A workspace may add keys of its own; the tools ignore keys they do not know.

### How research.yaml is found

1. `RMS_ROOT`, when set, names the folder. If that folder has no `research.yaml` the tools
   stop with `RMS_ROOT=... has no research.yaml`.
2. Otherwise the working directory and each of its parents, nearest first.
3. Otherwise the folder of the tool itself and its parents, which finds the workspace when
   the skill is installed inside it.

The post-install check (`bin/check.py`) uses 1 and 2 only.

## Environment variables

| Variable | Read by | Default | Effect |
|---|---|---|---|
| `RMS_ROOT` | every `research-dag` tool, every `bin/check.py` | unset | The folder holding `research.yaml`, overriding the upward search |
| `RESEARCH_DAG_HOME` | `dag_store.py`, `dag_update.py`, `validate_dag_references.py` | `~/.research-dags` | Where a store given as a URL or bare repository is cloned |
| `OPENALEX_EMAIL` | `openalex_discovery.py`, `sota_baseline.py` | `user@example.com` | Sent as `mailto`, which puts requests in OpenAlex's polite pool. Set it to an address you read |
| `S2_API_KEY` | `s2_ranking.py`, `sota_baseline.py` | unset | Semantic Scholar API key, raising its rate limit. `s2_ranking.py --api-key` wins over it |
| `SKILL_DIR` | every `bin/check.py` | the folder above the script | Which skill the check is for; installers set it |
| `SESSION_ID` | `branch_manager.py` | `S-000` | Recorded as `current_owner.session_id` in `metadata.yaml` |

Never commit `S2_API_KEY` or put it in `research.yaml`.

## Precedence

| Setting | Wins first | Then | Then |
|---|---|---|---|
| Workspace root | `RMS_ROOT` | nearest `research.yaml` above the working directory | nearest above the tool |
| The DAG `dag_update.py` edits | `--dag` | `dag_path` in `research.yaml` | `hypothesis-dag.yaml` in the working directory |
| The DAG `reconcile.py` reads | `--dag` | `research/hypothesis-dag.yaml` | |
| Store location | `dag_store.py --store` | `dag_store` | |
| Store project | `dag_store.py --project` | `dag_project` | |
| Store clone folder | `RESEARCH_DAG_HOME` | `~/.research-dags` | |
| Semantic Scholar key | `s2_ranking.py --api-key` | `S2_API_KEY` | none |
| Store or plain file | `dag_update.py --no-store` forces the plain file | both store keys set means the store | the plain file |

## hypothesis-dag.yaml

A mapping with a `nodes` list. Top-level keys other than `nodes` are kept as they are.
`metadata.primary_metric` is the DAG's metric; `dag_update.py --metric` warns when a new
node names a different one.

The fields `dag_update.py --action add` writes on a new node:

| Field | Type | Written as | Meaning |
|---|---|---|---|
| `id` | string | next id | Never changes |
| `parent` | id or null | `--parent` | The node that must resolve first. Change it only with `--action relink` |
| `hypothesis` | string | `--hypothesis` | The claim, specific and measurable |
| `status` | enum | `pending` | See [concepts](concepts.md#node-status) |
| `target_improvement` | number | `--target`, default `0.0` | The improvement that validates it |
| `metric` | string | `--metric`, else `metadata.primary_metric`, else `Unknown` | What is measured |
| `actual_performance` | number or null | `null` | Set by `--action update --performance` |
| `assigned_agent`, `branch` | string or null | `null` | Who works it, on which branch |
| `deliverables` | map | `blog`, `arxiv`, `pivot` all `null` | Links to the write-ups |
| `notes` | list or string | `[]` | Appended by `--action note` |
| `adoption` | map | see below | Whether the finding is live |
| `blocked_by` | list of ids | `[]` | Unrecorded preconditions: nodes that must land first |
| `contested_by` | list of ids | `[]` | Nodes whose findings challenge this one |
| `avenues` | list of ids | added to the parent | The node's children |

Other fields the tools read when present: `work_item_id`, `evidence`, `audit_findings`,
`golden_path`. `--action set --field NAME --value YAML` writes any field except `id` and
`parent`.

The `adoption` block:

| Field | Type | Default | Meaning |
|---|---|---|---|
| `state` | enum | `not_assessed` | `not_assessed`, `not_applicable`, `not_adopted`, `partial`, `adopted`, `contradicted` |
| `artefact` | string or null | `null` | Where in the running system the finding lives |
| `verification` | string or null | `null` | Shell predicate that exits 0 while the claim holds. Owed by `adopted`, `partial` and `contradicted` |
| `verified_on` | date or null | `null` | Set to today by `--action adopt` |
| `note` | string or null | `null` | Why the node sits at this state |

Example node:

```yaml
- id: H-001
  parent: H-000
  hypothesis: Adding day-of-week features lifts accuracy by at least 0.03
  status: validated
  target_improvement: 0.03
  metric: accuracy
  actual_performance: 0.845
  adoption:
    state: adopted
    artefact: src/features.py
    verification: python -c "import sys; sys.exit('day_of_week' not in open('src/features.py').read())"
    verified_on: 2026-09-30
    note: null
  blocked_by: []
  contested_by: []
```

## node-index.yaml

Written by `generate_node_index.py`; do not edit it. Keys: `source_dag`, `generated_at`
(UTC, ISO 8601), `total_nodes`, `ready`, `active`, and `framed` and `blocked` when not
empty. Each entry has `id`, `parent` and the first 120 characters of `hypothesis`; `active`
entries add `status` and `blocked` entries add `blocked_by`.

## Dashboard inputs

All optional.

| File | Shape | Fields the dashboard uses |
|---|---|---|
| `experiments_dir/*experiment-log.jsonl` | one JSON object per line | `experiment_id` or `id`, `node_id`, `timestamp`, `hypothesis`, `notes`, `success`, `improved`, `is_breakthrough`, `breakthrough_title`, `breakthrough_impact` |
| `breakthroughs` | `breakthroughs:` list | `id`, `experiment` or `experiment_id`, `node` or `node_id`, `title`, `description`, `impact`, `date` |
| `papers` | `papers:` list | `title`, `status`, `venue_target`, `key_result`, `path`, `nodes` (ids), `breakthroughs` (ids) |
| `findings_edges` | `findings_edges:` list | `from_node`, `to_node`, `relation`, `note` |

## metadata.yaml

Per research node, in the work item (or the folder given to `branch_manager.py
--target-dir`). Written by `branch_manager.py --action init`, read by `audit_verify.py`
from the working directory and by `/aar-sync-research-result`.

| Key | Meaning |
|---|---|
| `node_id`, `branch_name`, `status` | The node, its research branch, and `in_progress` or `awaiting_review` |
| `current_owner` | `id`, `session_id` and `role` of the agent holding it |
| `parent_performance` | The parent's measured result, fixed before the experiment |
| `target_improvement` | The target, fixed before the experiment |
| `actual_performance` | The measured result |
| `handoff` | `next_role`, `instructions`, `timestamp` |
| `milestones` | `baseline`, `implementation`, `benchmarking`, `synthesis`, each with a `status` |

`audit_verify.py` treats lower `actual_performance` as better (a loss or error metric).

## SKILL.md front matter

Each skill's `SKILL.md` opens with YAML front matter, per the
[Agent Skills specification](https://agentskills.io/specification):

| Key | Type | In this repository |
|---|---|---|
| `name` | string | Equals the folder name |
| `description` | string, at most 1024 characters, quoted | What the skill does and when to use it; agents choose skills by it |
| `license` | string | `CC-BY-4.0 AND Apache-2.0` with a pointer to `LICENSE` |
| `compatibility` | string, at most 500 characters | What it needs: `research.yaml`, Python, the AAW skills |
| `metadata.author` | string | `dermot-obrien` |
| `metadata.version` | quoted semver string | The skill's own version, bumped on any change inside its folder |
| `metadata.homepage` | URL | This repository |
| `metadata.x-skill-requires` | string | Comma-separated Package URLs with a semver range of the skills it needs, or empty |

## bundle.json

The bundle manifest installers read (DD-11 of AI-Assisted Work), validated by
`scripts/validate-bundle.mjs` against [`scripts/vendor/bundle.schema.json`](../scripts/vendor/bundle.schema.json).
Top level: `$schema`, `name`, `owner`, `description`, `license`, `homepage`, `skills`. Each
skill entry: `name`, `path`, `version` and `purl` (both equal to the `SKILL.md`
version), `requires` (each a `purl` and `range`, as `x-skill-requires` states them) and
`check` (`command`, `runtime`, `description`).

## framework.manifest.yaml

The AAW install engine's contract, read by `aar install`:

| Key | Value here | Effect |
|---|---|---|
| `id`, `name`, `version` | `aar`, `AI-Assisted Research (RMS)`, the framework version | Recorded under `modules.aar` in `.aaw-config.yaml` |
| `depends` | `[aaw]` | The install warns and exits 1 unless AAW is installed or a `.ai-assisted-work` clone is present |
| `runtime` | `python` | |
| `tool_setup.python.requirements` | `requirements.txt` | `pip install -r` unless `--no-python` |
| `skills.src` | `skills` | Each folder with a `SKILL.md` is copied to `.agents/skills/<name>/` |
| `config` | `research.yaml` from the example | Seeded only when absent |
| `data_dirs` | `[research/]` | Created in the workspace |

## .aaw-config.yaml

Written by AAW, not AAR. AAR's launcher reads `modules.aaw.source_root` to find the
install engine, and the research skills expect `work_items_path` there to match the one in
`research.yaml`.
