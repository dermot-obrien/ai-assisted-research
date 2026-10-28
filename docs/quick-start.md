<!--
SPDX-FileCopyrightText: 2026 Dermot O'Brien
SPDX-License-Identifier: CC-BY-4.0
-->

# Quick start

From an empty folder to a hypothesis DAG with a ready node, a node index, a dashboard, an
adoption check and a literature search, in about ten minutes, with an optional step that
keeps an experiment in a local vault and replays it. Every command below was run
as written on Windows, in PowerShell 5.1 and in Git Bash. Where the two shells differ, both
are shown.

You need Node 18 or newer, Python 3.10 or newer, git, and network access to GitHub. The
literature step also needs access to `api.openalex.org`. An AI agent is only needed for the
last step.

## 1. Create a workspace

AAR installs into a git repository, so start with one. Skip `mkdir .claude` unless you use Claude Code: the installer links the skills into `.claude/skills/` only when `.claude/` exists.

```bash
mkdir research-demo
cd research-demo
git init
mkdir .claude
```

The same four lines work in PowerShell.

## 2. Install the work skill and the research skills

The research skills hand work items to the `work` skill of [AI-Assisted Work](https://github.com/dermot-obrien/ai-assisted-work) (AAW), whose `bin/skills.mjs` is also the installer. Clone both repositories and install from the clones; no npm is involved.

```bash
git clone https://github.com/dermot-obrien/ai-assisted-work.git .ai-assisted-work
git clone https://github.com/dermot-obrien/ai-assisted-research.git .ai-assisted-research
node .ai-assisted-work/bin/skills.mjs install work
node .ai-assisted-work/bin/skills.mjs install --bundle .ai-assisted-research
python -m pip install -r .ai-assisted-research/requirements.txt
```

What you should see:

```text
installed work 3.1.1 from bundle ai-assisted-work (.claude/skills linked)
installed literature-discovery 1.1.4 from bundle ai-assisted-research (.claude/skills linked)
installed research-dag 2.0.0 from bundle ai-assisted-research (.claude/skills linked)
installed experiment-vault 1.0.0 from bundle ai-assisted-research (.claude/skills linked)
installed research 4.0.0 from bundle ai-assisted-research (.claude/skills linked)
```

The bundle is four skills: `research` (the flows), `research-dag` (the DAG tools the steps
below run), `experiment-vault` (step 10) and `literature-discovery` (step 9).

Install `work` first. The other way round it still installs, with `note: research says it needs work, which is not installed`. The work version may be newer than shown. In a real repository, add `.ai-assisted-work/` and `.ai-assisted-research/` to `.gitignore`, or clone them somewhere else and give their paths.

## 3. Create research.yaml and check the installation

The `/research start` and `/research init` flows create `research.yaml` and the research folder for you. This walkthrough uses the tools before any flow, so copy the example by hand, and tell `work` to keep its work items where the example's `work_items_path` expects them:

```bash
cp .agents/skills/research/assets/research.yaml.example research.yaml
mkdir research
echo 'work_items_path: ".aaw/work-items/"' > .aaw-config.yaml
```

In PowerShell, `cp` and `mkdir` work as written; use `Set-Content -Path .aaw-config.yaml -Value 'work_items_path: ".aaw/work-items/"' -Encoding ascii` for the `echo` line. Without `.aaw-config.yaml`, `work` keeps work items in `change/work-items/`, and you would then change `work_items_path` in `research.yaml` to match.

Each skill ships a post-install check. Run the research skill's:

```bash
python .agents/skills/research/bin/check.py
```

```text
warning: research.yaml: dag_path research/hypothesis-dag.yaml does not exist yet; the first hypothesis creates it.
warning: research.yaml: node_index_path research/node-index.yaml does not exist yet; generate_node_index.py writes it.
warning: research.yaml: work_items_path .aaw/work-items/ does not exist yet; starting a research work item creates it.
research: ok
```

The warnings are expected in a new workspace. A line without `warning:` is a problem; see [troubleshooting](troubleshooting.md). The `research-dag` check prints the same, and `experiment-vault`'s prints `experiment-vault: ok`. `node .ai-assisted-work/bin/skills.mjs check` confirms the installed copies match what was installed.

## 4. Write a tiny DAG

The hypothesis DAG is a YAML file. Start it with a root node that records the baseline you
are trying to beat.

PowerShell:

```powershell
$dag = @'
metadata:
  primary_metric: accuracy
nodes:
- id: H-000
  hypothesis: Baseline. A logistic regression on the raw features scores 0.81 accuracy.
  status: validated
  parent: null
  actual_performance: 0.81
'@
Set-Content -Path research/hypothesis-dag.yaml -Value $dag -Encoding ascii
```

Bash:

```bash
cat > research/hypothesis-dag.yaml <<'EOF'
metadata:
  primary_metric: accuracy
nodes:
- id: H-000
  hypothesis: Baseline. A logistic regression on the raw features scores 0.81 accuracy.
  status: validated
  parent: null
  actual_performance: 0.81
EOF
```

## 5. Add a hypothesis

Change the DAG through `dag_update.py`, never by hand, so ids, parents and statuses stay
consistent:

```bash
python .agents/skills/research-dag/bin/dag_update.py --dag research/hypothesis-dag.yaml --action add --parent H-000 --hypothesis "Adding day-of-week features lifts accuracy by at least 0.03" --plain-tested "Whether knowing the day of the week helps predict better" --target 0.03 --metric accuracy
```

```text
Added new node: H-001
```

Open `research/hypothesis-dag.yaml`: H-001 is there with `status: pending`, an `adoption`
block at `not_assessed`, and H-000 lists it under `avenues`.

## 6. Compute what is ready

The research skills read readiness from the node index rather than walking the DAG:

```bash
python .agents/skills/research-dag/bin/generate_node_index.py
```

```text
Node index generated: ...\research\node-index.yaml
  Total nodes: 2
  Ready: 1
  Active: 0
  Framed: 0
  Blocked: 0
```

H-001 is `ready` because its parent is resolved (`validated`).

## 7. Check references and build the dashboard

```bash
python .agents/skills/research-dag/bin/validate_dag_references.py
python .agents/skills/research-dag/bin/generate_dashboard.py
```

```text
DAG contains 2 hypothesis IDs
All hypothesis ID references are registered in the DAG.
Generating research dashboard...
  Nodes: 2
  ...
  Dashboard: ...\research\dashboard.html
```

Open `research/dashboard.html` in a browser (`start research/dashboard.html` in either
Windows shell, `open` on macOS, `xdg-open` on Linux). You should see H-000 as a green
(validated) node and H-001 as a grey (pending) node with a pulsing amber border, meaning
ready, and `Ready (1)` in the side panel. The graph loads D3 from the web, so the page
needs a connection.

## 8. Run the adoption check

`status` says whether a hypothesis is true; `adoption.state` says whether it is live in the
running system. `reconcile.py` checks the second. H-000 was written by hand without an
`adoption` block, so seed one first:

```bash
python .agents/skills/research/scripts/reconcile.py --dag research/hypothesis-dag.yaml --migrate
python .agents/skills/research/scripts/reconcile.py --dag research/hypothesis-dag.yaml
```

```text
migrate: 1 node(s) given a default adoption block
...
Adoption states
  not_assessed     2

No drift.
```

It exits 0. Run the second command before migrating and it exits 1 with a
`no_adoption_block` finding.

## 9. Search the literature

```bash
python .agents/skills/literature-discovery/bin/openalex_discovery.py --query "calendar features tabular classification" --limit 3 --output research/papers-found.yaml
```

```text
Searching OpenAlex for: 'calendar features tabular classification'...
Saved 3 results to research/papers-found.yaml
```

Set `OPENALEX_EMAIL` to an address you read to use OpenAlex's polite pool. The
`sota_baseline.py` tool in the same folder also asks Semantic Scholar, which often answers
`429` without an `S2_API_KEY`; see [troubleshooting](troubleshooting.md#literature-discovery).

## 10. Keep the run in a local vault (optional)

The experiment vault keeps a run's code, data, environment, command and outputs as a capsule
that can be run again. A folder inside the workspace serves for a try. A capsule pins a
commit, so commit first, with the clones and the folders the run writes git-ignored. This
step was checked in Bash; in PowerShell, write the two files with an editor and run the
`git` and `python` lines as they are.

```bash
cat > evaluate.py <<'EOF'
import json, os
os.makedirs("out", exist_ok=True)
json.dump({"accuracy": 0.845}, open("out/metrics.json", "w"))
EOF
printf '.ai-assisted-*/\nvault/\nout/\n.vault-replay/\n' > .gitignore
git add -A
git commit -m "Day-of-week experiment"
python .agents/skills/experiment-vault/bin/vault.py --vault vault --project demo init
python .agents/skills/experiment-vault/bin/vault.py --vault vault --project demo run --node H-001 --outputs out --metrics out/metrics.json --metric accuracy -- python evaluate.py
```

```text
Initialised .../research-demo/vault
note: PYTHONHASHSEED is not set, so set and dict-of-str iteration order can differ between runs; set it for bit-identical replays
Capsule H-001/20261021T044351Z-b8c8403bcd39: 4 files, 851.5 KB, 4 new to the vault
  .../research-demo/vault/capsules/demo/H-001/20261021T044351Z-b8c8403bcd39.json
Recorded on H-001: capsules += 20261021T044351Z-b8c8403bcd39
```

H-001 now has a `capsules` list naming the capsule and its hash. Replay it with the capsule
id your run printed; `--setup none` uses this Python as it is instead of building a fresh
environment from the capsule's package list:

```bash
python .agents/skills/experiment-vault/bin/vault.py --vault vault --project demo replay H-001/<capsule id> --setup none
```

```text
Restored H-001/20261021T044351Z-b8c8403bcd39 into .../research-demo/.vault-replay/20261021T044351Z-b8c8403bcd39
Verdict: identical (rtol 1e-09, atol 1e-12)
  ok  accuracy: was 0.845, now 0.845 (delta +0)
  outputs: 1 identical, 0 changed
Capsule H-001/20261021T044352Z-ce56c6437fda: 4 files, 851.5 KB, 0 new to the vault
  ...
Recorded on H-001: capsules += 20261021T044352Z-ce56c6437fda
```

The replay is itself kept, as a `retest` capsule. In a real workspace, set `vault.uri` in
`research.yaml` instead of passing `--vault`; see
[configuration](configuration.md#the-experiment-vault).

## 11. Hand a hypothesis to your agent

Everything so far ran without an agent. The `research` skill's flows are the workflows an agent runs
on top of these tools. Open the folder in your agent and ask:

```text
/research frame H-001
```

or, in plain words, "frame hypothesis H-001". The agent reads the node index, delegates to
`/work start` to create a work item under `.aaw/work-items/`, records the work item on
the node and moves it to `framed`. From there, `/research run {WI_id} H-001`
runs the experiment and `/research sync H-001 {WI_id}` records the result. The
[user guide](user-guide.md) walks the whole cycle.

## Clean up

Delete the `research-demo` folder. Everything the walkthrough made, the clones included, is inside it.

## Next

- [Concepts](concepts.md): the ideas behind what you just ran.
- [Skills](skills.md): what each skill and research flow does and when to use it.
- [Commands](commands.md) and [configuration](configuration.md): every flag and key.
