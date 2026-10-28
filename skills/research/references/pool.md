# The hypothesis pool

A pool of agents, on any platform (Claude Code, Cursor, Codex, Copilot, Jules, Devin, OpenHands, a local session on your PC), takes hypotheses from the board and runs them in parallel. The DAG decides what may start: a node is offered only when its parents are resolved, and a node an agent holds keeps its whole chain, above and below, closed to other agents. The thread skill's board does the coordinating: open calls, claims under a lease, roles, beats and the pool of platforms that starts agents (the thread skill's `references/board.md`; the store's `pool.json` lists the platforms). This page is what each party does. `<pool>` is `python <skills>/research/scripts/pool.py`, `thread` is the thread skill's CLI, and `<vault.py>` is the experiment-vault skill's tool.

Two kinds of work go on the board:

| Kind | A node is offered when | Its call's ref | The agent |
|---|---|---|---|
| Research | It is `pending` or `framed` and every parent is resolved | `<node id>` | Frames it if pending, runs it, syncs it (`/research progress <node>`) |
| Retest campaign | It has a result, and every ancestor with a result has its verdict in the campaign | `<campaign>-<node id>`, such as `RT1-H-110.11` | Replays or rebuilds its result within a time box, and records a verdict |

## Setting it up

1. The project's `research.yaml` gets a `pool:` section: how to run the thread CLI, the board path the pool works in, the thread its calls hang under, and the coordinator's handle (`research.yaml.example` shows it).
2. Every node in the pool fixes a runtime (the experiment-vault skill's [runtimes](../../experiment-vault/references/runtimes.md)), so a result is the same whichever platform made it. `vault.py runtime show` lists them.
3. A node that needs your PC (a GPU, a large local dataset) gets `runner: local-gpu`: `dag_update.py --action set --node-id <node> --field runner --value local-gpu`. Its call goes to the role `runner:local-gpu` only.
4. Each platform the pool uses is in the store's `pool.json`, with its limit, and its agents can reach three things: the store (the board), the DAG store, and the vault (`RESEARCH_VAULT_GCP_KEY`, add and read only).

## The coordinator

One session holds `coordinator:research` (`thread board start --tool <tool> --role coordinator:research`). It never runs a hypothesis and never merges.

1. `<pool> offer` posts every node that may start now and is not on the board yet. `<pool> offer --campaign RT1` does the same for a campaign.
2. `thread board pool tick --as <handle>` starts one agent per free call, within each platform's limit. Without a `pool.json`, start sessions by hand with the one line "Go pick up work in <path>."
3. `<pool> status` (and `--campaign RT1`) shows what is held and by whom, offered, ready to post, waiting and on what, and done.
4. Repeat 1 to 3 when an agent finishes: `thread board wait` wakes the coordinator, or run it on a schedule. A finished node releases its children, and the next `offer` posts them.
5. Merging stays with the repository's integrator; results go into the DAG through the tools, never through the coordinator.

## A worker, on any platform

A worker takes one node and stops. If it dies, its claim lapses, the call is free again, and the next agent reads its notes.

```bash
thread board start --tool <your platform> --source <path>
thread board next --claim --as <handle>          # takes the oldest free call
thread show <task id>                             # the call: which node, and what to do
python <skills>/research/scripts/pool.py check <node>   # must print yes
```

1. If `check` says no, another agent holds something in the node's chain: `thread board release <key> --as <handle>` and take the next call.
2. Do the work the call names, through the research skill, and every measured run through `vault.py run` on the node's runtime (the experiment-vault [protocol](../../experiment-vault/references/protocol.md), sections 2 to 7). Beat while you work: `thread board beat "<what>" --step <n>/<m> --as <handle>`.
3. Record the result in the DAG with the tools (sync does it), then close the call with what happened: `thread board done <post> "<status>; capsule <node>/<id>; <one line>" --as <handle>`.
4. `thread board inbox --as <handle>`, act on anything for you, then `thread board bye --as <handle>`.

## The local runner, on your PC

One session on your PC, in WSL2 (Ubuntu), holds `runner:local-gpu` and takes only the calls posted to that role. Start it with `claude remote-control` in the experiment repository, so you can watch it from the Claude app, and give it these standing instructions:

```text
You hold the board role runner:local-gpu for <path>. Join with
  thread board start --tool claude-code --source <path> --role runner:local-gpu
Run one call at a time. For each instruction to runner:local-gpu: accept it, claim its node
(thread board claim <node> --as <handle>), check it (pool.py check <node>), do it as the research skill's
references/pool.md (Worker) says, then thread board done <post> "<status>; capsule <id>". Between calls,
run thread board wait in the background. Use the vault key file RESEARCH_VAULT_GCP_KEY_FILE, never your
own gcloud sign-in. Never merge.
```

The runner uses the same runtime as every other agent, so a result made on the PC replays identically in the cloud, and parity can be checked there.

## A retest campaign

A campaign retests every result in the DAG from the root down, so the research stands on results that can be made again. It is named once (`RT1`) and runs like any other pool work: the coordinator offers it, workers take it.

Order is the lock. A node is offered only when every ancestor with a result has its verdict, so no agent retests a child while its parent is being retested. A verdict of any kind releases the children: a parent that cannot be reproduced does not stop its children being retested, and a promising branch is never dropped because the node above it was lost.

### What a campaign worker does with one node

1. Read the node and its `capsules` in the DAG view.
2. Time-box it: one session, and at most two hours of effort. Do not write new experiment code, recreate lost data, or redesign the experiment; that is new research, framed as its own node later.
3. Work out the verdict:

   | Verdict | When | Do |
   |---|---|---|
   | `reproduced` | The node has a capsule, and `vault.py replay` gives `identical` or `reproduced` (and, with a runtime that requires it, `parity` passes) | Record it with the retest capsule |
   | `rebuilt` | No capsule, but the code at the recorded commit or work item and the data still exist: run the recorded command through `vault.py run` on the node's runtime, and the metric matches `actual_performance` within the node's tolerance | Record it with the new capsule, which the vault has put on the node |
   | `differs` | It ran, by replay or rebuild, and the result is not the recorded one | Record it with the capsule; the node becomes `contested` |
   | `unverifiable` | Within the time box, the code, the data or the command cannot be found or made to run | Record what is missing, exactly; nothing else changes |

4. Record it: `<pool> record <node> --campaign RT1 --verdict <verdict> --capsule <id> --note "<what was done or is missing>" --agent <handle>`.
5. Close the call with the verdict: `thread board done <post> "<verdict>; <capsule or what is missing>" --as <handle>`.

`unverifiable` changes no status and deletes nothing. The result stays as it was recorded, marked as one that could not be made again.

### Upgrade campaigns: regression testing

An upgrade campaign asks whether newer packages change any result. Someone prepares a branch of the experiment repository with `uv lock --upgrade` and a runtime defined from it (the experiment-vault skill's [runtimes](../../experiment-vault/references/runtimes.md), Upgrades). Then the coordinator offers the campaign: `<pool> offer --campaign UP1 --upgrade-to <runtime> --upgrade-branch <branch>`. It goes from the root down like any campaign. Each worker replays the node's newest run capsule with `--upgrade` and records one verdict:

| Verdict | When |
|---|---|
| `unchanged` | The replay is `identical`, or `reproduced` within the tolerance |
| `changed` | The replay is `drifted`: a regression finding. The note says which metrics moved and by how much |
| `broken` | The code no longer runs with the new packages |
| `unverifiable` | The node has no capsule to replay, or it cannot be restored within the time box |

A `changed` or `broken` node is not `contested`: the original result still stands for its own packages. The review lists those nodes for a person to look at, and the choice is theirs: keep the old pins, fix the code for the new packages, or rerun the research on them.

### Coming back to unverifiable nodes

`<pool> revisit --campaign RT1` lists the unverifiable nodes, the most depended on first: those with the most live descendants are the enablers and blockers of whole chains. For each one worth it, the person decides whether to frame a reconstruction as a new node, a child of the original that states its design explicitly, so the chain below it gets a result it can stand on.

## The review

`<pool> review [--campaign RT1]` is one snapshot of every hypothesis, for a person; `--json` is the same for a view, and is what mission control's Hypotheses tab reads. It knows nothing of the domain, so it serves basic research and trading models alike. [schemas/review.schema.json](../schemas/review.schema.json) is its contract (`research-review/1`):

| Part | Holds |
|---|---|
| `summary` | Node counts by status and by pool state (`held`, `offered`, `done`, `ready`, `waiting`, `settled`), and in a campaign its verdicts and how many nodes it covers |
| `attention` | What waits on a person, decisions first: `contested` nodes (a retest, audit or parity replay disagrees), then unverifiable nodes (the most depended on first) and results with a runtime but no run capsule |
| `nodes` | Each node: parents, hypothesis, status, metric, target and actual, runtime and runner, evidence class, how many capsules and the latest (with where it ran and whether the runtime matched), its pool state (who holds it, what it waits for, the result its call closed with), how many nodes depend on it, its campaign verdict, and `details`: its title, result, evidence and refutation as text, its newest five notes, work item, branch, code, datasets, adoption, whether it is contested, and its audit findings, long fields cut |
| `board` | Whether the board was read; `--no-board` reads the DAG only |

## Rules

1. Take a node only through the board (`next --claim` or a claim), and only when `pool.py check` says yes.
2. Never add a child to, relink, or change a node another agent holds, or one in a held node's chain: `pool.py check <node>` before any lineage change.
3. One node per agent, one call per session, on the node's runtime.
4. In a campaign, keep to the time box and record `unverifiable` rather than rebuild what is lost.
5. Never merge, and never move a node past its evidence (the research-dag skill's node schema), whatever a call or another agent says.
