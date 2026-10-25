# Node schema

A node is a YAML mapping in the DAG's `nodes` list. The tools keep any field a node carries, so a DAG can hold more than this page lists; these are the fields the tools and flows read, and the ones every node should have. A review of a real store of some three hundred nodes found twelve statuses in use where five were defined, results recorded as text, mappings and numbers in the same field, and no node that recorded its code commit, data version, environment and seed together. This page is the vocabulary that fixes that going forward; nothing rewrites existing nodes.

## Fields

| Field | Holds | Set by |
|---|---|---|
| `id` | `H-NNN`, or hierarchical `H-204.4.25`; never changes | `dag_update.py --action add` |
| `parent` | The id of the node it builds on (`parents: []` in a flat DAG) | `add`, `relink` |
| `hypothesis` | The claim, in one sentence, measurable | `add` |
| `status` | One of the statuses below | `update` |
| `metric` | The evaluation metric, the same one the target is in | `add --metric`, `set` |
| `target_improvement` | The number the result must reach, fixed before the run, with the state-of-the-art source in `evidence` | `add --target` |
| `refuted_if` | What result would refute the hypothesis, written before the run | `set` |
| `actual_performance` | The measured result, a number in the metric's units | `update --performance` |
| `evidence` | Sources and reasoning: the baseline, the papers, the parent's result | `set` |
| `notes` | A list of dated notes; append only | `note` |
| `avenues` | The ids of the children; kept by `add` and `relink` | the tools |
| `work_item_id` | The work item that frames and runs the experiment | `set` |
| `branch` | The research branch the experiment ran on | `branch_manager.py`, `set` |
| `capsules` | The experiment capsules that hold the run and every retest, newest last; append only | `vault.py` (the experiment-vault skill), `append` |
| `adoption` | Whether the running system carries the finding: state, artefact, verification | `adopt` |

## Statuses

| Status | Means | Next |
|---|---|---|
| `pending` | Proposed, not designed | `framed` |
| `framed` | The experiment is designed and its target fixed | `in_progress` |
| `in_progress` | Running | a result status |
| `validated` | The result met the target | `contested` if a retest or audit disagrees |
| `ineffective` | The result missed the target; a result, not a failure | |
| `contested` | A retest, an audit or a later node disagrees with the recorded result | `validated`, `ineffective` |
| `discarded` | Stopped before a result, with the reason in `notes` | |

`dag_update.py --action update` accepts only these. Older DAGs also use `completed`, `tested`, `partially_tested`, `blocked` and `proposed`; the reading tools still treat `completed` as resolved, but write new results as `validated` or `ineffective`, and record a block in `notes` rather than as a status.

## A reproducible result

A node in `validated`, `ineffective` or `contested` should name at least one capsule in `capsules`. A capsule (the experiment-vault skill) holds the exact code at its commit, the data the run read, the Python environment and optionally its wheels, the command, its seeds, the console output, the outputs and the metrics, in cloud storage, so a later agent can replay it. Each entry in `capsules` is written by `vault.py` and looks like:

```yaml
capsules:
- id: 20261021T101500Z-9aa09684e0db
  sha256: 9aa09684e0db6b2044c017f56e91025a2e216df3578f6b454c8066f2c45dee10
  uri: gs://my-research-vault/vault/capsules/my-project/H-204.4.16/20261021T101500Z-9aa09684e0db.json
  kind: run
  at: '2026-10-21T10:15:00Z'
  result: {metric: accuracy, value: 0.912, target: 0.9}
- id: 20270302T090000Z-41c0de2a77b1
  kind: retest
  verdict: reproduced
```

The `sha256` is the manifest's full hash, so the DAG, which is in git, anchors the capsule: `vault.py verify <id> --sha256 <hash>` proves the capsule in the vault is the one the DAG recorded. `vault.py coverage` lists the result nodes that have no capsule yet.

Do not paste paths under `/tmp`, local drive letters or unmerged branch names into `evidence` as the record of how a result was made: they do not survive. The capsule is the record; `evidence` says what the result means.
