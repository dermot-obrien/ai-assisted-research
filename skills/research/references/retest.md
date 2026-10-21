# Retest

Usage: `/research retest {node_id} [what changed]`, for example
`/research retest H-204.4.16 "numpy 2.1"` or `/research retest --all-validated "new prices.csv"`

A recorded result is a claim about the world at one moment: one commit, one dataset, one set of library versions. This flow checks whether the claim still holds after something changed, from the capsule the result was made from, and records what it finds on the node either way. It needs the experiment-vault skill and `vault` set in `research.yaml`.

## Phase 1: Find what to retest

1. **Pull the DAG** (`dag_store.py view`, with a store) and read the node. Take its newest capsule of kind `run` from `capsules`; with none, the result cannot be retested from a record. Say so, suggest `/research run` to make one, and stop.
2. **Check the capsule is intact**: `vault.py verify <node>/<capsule> --sha256 <hash from the node>`.
3. **Name the change**, from the user's words or by asking: a library version, the environment as a whole, the code, or the data. With `--all-validated`, do this for every `validated` node with a capsule that the change touches (a node whose capsule's lock names the library, or whose `data[]` names the dataset); list them and confirm before running more than three.

## Phase 2: Replay with the change

| What changed | Run |
|---|---|
| Nothing, or "does it still reproduce" | `vault.py replay <capsule>` |
| A library | `vault.py replay <capsule> --pip <package>==<version>` |
| The environment as a whole | `vault.py replay <capsule> --setup none`, in the new environment |
| The code or the data | Commit the change, then `vault.py run --node <node> --retest-of <capsule> <the capsule's --data, --outputs, --metrics, --metric and --seed> -- <the capsule's command>` |

Pass `--note "<what changed>"` and your `--agent` handle. Each records a `retest` capsule on the node with its verdict. Read the command, paths and seeds from `vault.py show <capsule>`, never from memory.

## Phase 3: Record the outcome

| Verdict | On the node |
|---|---|
| `identical` or `reproduced` | `dag_update.py --action note --node-id <node> --note "Retest <date> (<what changed>): <verdict>, capsule <id>"`. The status stays. |
| `drifted` | The note, with each metric that moved, was and now. Then, for a `validated` or `ineffective` node, `dag_update.py --action update --node-id <node> --status contested`, and `--action set --field contested_by --value <retest capsule id>`. |
| `failed` | The note, with the error from the capsule's stderr. Leave the status: a retest that cannot run says nothing about the claim. Fix the replay (a missing system library, a moved data path) and retest again. |

Then recompute the node index. A `contested` node is a question for the user, not a conclusion: say which result moved, by how much, under which change, and propose either a new child hypothesis that explains the change or `/research audit`. Do not set the node back to `validated` yourself.

## Model leeway

The workflow is mandatory. The tools are a reference implementation: find better ways to execute the steps if you can, provided you follow the process and adhere to the project's research principles ([principles.md](principles.md), or the workspace's own copy where it governs one).

## Related skills

- `/research audit` checks a result is sound, which a replay alone does not.
- `/research run` makes the first capsule when a node has none.
- The experiment-vault skill's [replaying](../../experiment-vault/references/replaying.md) has every replay option.
