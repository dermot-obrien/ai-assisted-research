# Pool playbook

How to run hypotheses with a pool of agents on several platforms at once (Claude Code, Cursor, ChatGPT Codex and others), coordinated through the thread skill's board, with every result made in a pinned runtime so it is the same whichever agent made it. The same steps run a retest campaign over the whole DAG. The research skill's [pool reference](../skills/research/references/pool.md) is what the agents follow; this page is what you set up and do.

![Architecture of the hypothesis pool](architecture.svg)

## What you need first

| Thing | What it is | Where it is set up |
|---|---|---|
| The vault | The bucket and its add-and-read-only key, `RESEARCH_VAULT_GCP_KEY` | [Storage](../skills/experiment-vault/references/storage.md) |
| The DAG store | The shared DAG, a git repository | [DAG store](../skills/research-dag/references/dag-store.md) |
| The board | The threads store, a git repository every agent can push to | The thread skill's `references/setup.md` |
| The experiment repository | Has `research.yaml` with `dag_store`, `vault` and `pool:`, a uv project with `uv.lock`, and the skills under `.claude/skills/` | This bundle's README |
| A runtime | The machine type, Python build, lock and settings evidence runs must match | [Runtimes](../skills/experiment-vault/references/runtimes.md) |

Every agent, on every platform, needs the same five things: Python 3.10+, git, Node 18+ (for the board), uv, and network access to GitHub, PyPI, Google's storage and OAuth hosts, and uv's Python downloads. And three credentials: the vault key, push access to the board's store, and push access to the DAG store.

## 1. Prepare once

1. **Pick or define the runtime.** In the experiment repository, on x86-64 Linux (a cloud session, or WSL2 on your PC):

   ```bash
   uv python install 3.12.8
   uv sync --frozen --python 3.12.8 --managed-python
   python .claude/skills/experiment-vault/bin/vault.py runtime create lx-py3128-v1 --python .venv/bin/python
   ```

2. **Fix it on the nodes the pool will run**, and mark any that need your GPU:

   ```bash
   B=.claude/skills/research-dag/bin
   python $B/dag_update.py --action set --node-id H-110.11 --field runtime --value lx-py3128-v1
   python $B/dag_update.py --action set --node-id H-142 --field runner --value local-gpu
   ```

3. **Add the pool section** to `research.yaml` (paths for your machine):

   ```yaml
   pool:
     thread: "node .claude/skills/thread/bin/thread.mjs"
     source: "research"
     on_thread: "t-xxxx"        # a thread for the pool: thread open "Hypothesis pool" --source research
     as: "coordinator"
   ```

4. **Set a cap** on how many agents may run, as a standing order on the board, so the pool never outruns your budget:

   ```bash
   thread board post "At most 4 agents in research at once; one hypothesis per agent; campaign time box 2 hours." --to '*' --kind standing --for-user --as <your handle>
   ```

5. **List the platforms** the coordinator may start agents on in the store's `pool.json` (`thread board pool help` shows the format). Start with two platforms and a max of two each.

## 2. Set up each platform

Do each platform once. The three credentials go in as secrets, never in a file or a prompt.

### Claude Code (cloud sessions)

1. In the cloud environment's settings, add the repositories: the experiment repository, the board's store and the DAG store (`patternode/research-dags`). The session's GitHub access then covers the store and the DAG store.
2. Add the environment variable `RESEARCH_VAULT_GCP_KEY` (the key on one line, or in base64).
3. Add to the setup script: `pip install uv` (and `npm` is already there for the board).
4. Set `VAULT_AGENT_TOOL=claude-code` in the environment variables.
5. To start one by hand: a new session on the experiment repository with the prompt `Go pick up work in research.`

### Cursor (cloud agents)

1. Create an environment with the experiment repository, the store and the DAG store selected (multi-repository environment).
2. In Cloud Agents → Secrets, add `RESEARCH_VAULT_GCP_KEY` as a **Runtime Secret**, and `THREADS_REMOTE` as a token URL to the store if the environment's git cannot push to it.
3. In `.cursor/environment.json`, an `install` step: `pip install uv`, and `VAULT_AGENT_TOOL=cursor`.
4. Add `cursor` to `pool.json` (the `cursor` preset) with its API key's variable, so `pool tick` can start agents.

### ChatGPT Codex (cloud)

1. Create an environment with the experiment repository (and the store and DAG store if your plan allows several).
2. Turn on internet access, with the **Package managers** preset plus custom domains: `storage.googleapis.com`, `oauth2.googleapis.com`, `github.com`, `objects.githubusercontent.com`.
3. Add `RESEARCH_VAULT_GCP_KEY` and `THREADS_REMOTE` as **environment variables** (setup-time secrets are removed before the agent runs, so they would not reach it). The task can see them, which is why the vault key can only add and read.
4. In the setup script: `pip install uv`, and `export VAULT_AGENT_TOOL=codex`.
5. Add `codex` to `pool.json` as a `command` starter (`codex cloud exec ...`), or start tasks by hand with `Go pick up work in research.`

### Copilot, Jules, Devin, OpenHands

The same three credentials as each platform's secrets, `pip install uv` in its setup, its `VAULT_AGENT_TOOL`, and its preset in `pool.json`. The fact sheets in the thread repository (`docs/integration/platforms/`) say where each keeps secrets and what its network allows; Copilot's firewall needs the Google hosts and `github.com` added.

### Your PC (the GPU runner)

1. In WSL2 (Ubuntu), clone the experiment repository and run step 1.1 there, so the PC matches the runtime: `vault.py runtime check lx-py3128-v1 --python .venv/bin/python` must say it matches.
2. Save the vault key to a file readable only by you and set `RESEARCH_VAULT_GCP_KEY_FILE` to it, so the runner never uses your own gcloud sign-in.
3. Start the runner: `claude remote-control` in the repository, and give it the standing instructions in the [pool reference](../skills/research/references/pool.md#the-local-runner-on-your-pc). It holds `runner:local-gpu` and takes only nodes marked `runner: local-gpu`.
4. Keep the PC awake while it runs.

## 3. Run the pool

1. **Start the coordinator**: one session (any platform; your PC is fine) that holds the role. Tell it:

   ```text
   You are the coordinator for the hypothesis pool. Join the board with
   thread board start --tool <tool> --source research --role coordinator:research
   Then loop: python .claude/skills/research/scripts/pool.py offer; thread board pool tick;
   python .claude/skills/research/scripts/pool.py status; thread board wait. Never run a hypothesis,
   never merge, and keep to the standing orders.
   ```

2. **Watch it**: `pool.py status` (held, offered, waiting, done) and `thread board review` (agents, beats, blockers, usage). A quiet or blocked agent shows there.
3. **Merge their pull requests**: workers open pull requests for code and post them ready; the repository's integrator merges in queue order, as for any other work.
4. **Stop**: retract the standing order, or set `pool limit <platform>`; agents finish their node and stop.

## 4. Run a retest campaign

1. Pick an id, `RT1`, and tell the coordinator to offer the campaign: `pool.py offer --campaign RT1` in its loop instead of `pool.py offer`.
2. Each worker retests one node within the time box and records one verdict: `reproduced`, `rebuilt`, `differs` or `unverifiable`. The order is top-down; a verdict of any kind releases the children.
3. Follow it with `pool.py status --campaign RT1`, which counts the verdicts.
4. When it is done, `pool.py revisit --campaign RT1` lists the unverifiable nodes, the most depended on first. Decide which ones are worth a reconstruction, and frame each as a new child node that states its design explicitly.

## Keeping it in proportion

- **Start small.** Two or three agents on one platform until a few nodes have gone through cleanly, then add platforms.
- **Time-box retests.** Two hours and one session per node. Lost code or data means `unverifiable` with what is missing, not a rebuild from scratch. The record stays, and the node can be revisited when it turns out to matter.
- **Watch the usage.** `thread board review` shows starts and units per platform; `thread board pool limit <platform> --for 5h` pauses one that hits its quota.
- **One node, one agent, one session.** A node too big for one session is split in the DAG before it is offered.
- **Parity costs a second run.** It is what makes a result platform-independent; for a long campaign, the replay can be done by a cheaper platform.

## When something goes wrong

| What you see | What it means | Do |
|---|---|---|
| A call held for hours with no beat | The agent died or stalled; its claim lapses after its lease | Nothing: the call frees itself and the next tick starts another agent |
| `cannot be evidence` in an agent's report | It ran outside the runtime | Fix the platform's setup (Python, uv, the lock), then let it retry |
| `has no identical replay on another machine` | Parity is pending | Leave it: a later agent on another platform replays it, or start one |
| A `differs` verdict | The recorded result does not reproduce; the node is now `contested` | Read both capsules (`vault.py show`); decide whether the old result or the new run is wrong |
| Nothing offered, agents idle | Everything ready is held or done, or the rest waits on held nodes | `pool.py status` shows what waits on what |
