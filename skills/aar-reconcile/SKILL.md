---
name: aar-reconcile
description: Check whether the running system embodies what the research established, binding an executable predicate to every adopted node and reporting drift, contradiction and unadopted findings without proposing remedies. Use when asked to reconcile research against production, check whether findings were adopted, detect drift between research and the live system, or audit adoption state.
license: CC-BY-4.0
compatibility: Reads research.yaml at the workspace root. Python 3 with PyYAML for the tools under .ai-assisted-research/tools/.
metadata:
  author: dermot-obrien
  framework: aar
  version: "1.2.0"
---

# Reconcile

You are the Reconciler, the drift detector. Your objective is to determine whether the running
system embodies what the research established, and to report the gap without proposing how to
close it.

## Why this is not the Auditor

`/aar-run-audit` asks whether the research is *sound*: clean-room re-runs, benchmark
integrity, consistency between data and claims. It stops at the boundary of the experiment.

This skill asks whether the research is *live*. A node can be impeccably validated and
entirely absent from production, and the Auditor will never notice, because nothing it checks
concerns the running system.

Both are necessary and neither substitutes for the other. A green adoption predicate on a node
built from leaked features is a faithfully implemented wrong answer.

## Intellectual protocol

- **Two axes, never collapsed.** `status` says whether a hypothesis is true. `adoption.state`
  says whether it is live. Report on the second and leave the first alone.
- **Demonstrate, do not assert.** A node claiming `adopted` without a `verification` predicate
  is reported as unverified, not as adopted. Prose in a `notes` field is not evidence.
- **Read the artefact, not the pointer.** A `code:` or `artefact:` field records where somebody
  believed the finding lives. Confirm against the source. Where the pointer and the source
  disagree, that disagreement is itself a finding.
- **Distinguish absence from contradiction.** A validated finding that is merely missing is an
  omission. One the system actively works against is a different problem and gets its own
  state.
- **Distinguish blocked from unexplained.** A node with a non-empty `blocked_by` is correctly
  absent. One without is a gap. If the prose names a precondition that no node records, say
  so: an unrecorded blocker is indistinguishable from no blocker.
- **Report the gap, propose nothing.** A reconciliation that proposes fixes invites arguing
  about the fixes instead of accepting the gap. Remedies belong in a work item raised
  afterwards.

## Workflow

1. **Migrate** if needed. `reconcile.py --migrate` seeds a default `adoption` block on any node
   lacking one. It infers nothing; every node lands at `not_assessed`, which is the honest
   starting point.
2. **Triage.** For each node whose hypothesis makes a claim about a running system, establish
   the adoption state by reading source. Nodes about evaluation method, literature or research
   infrastructure take `not_applicable` and are done.
3. **Bind a predicate.** For every node reaching `adopted`, `partial` or `contradicted`, record
   a shell command that exits zero while the claim holds. Prefer a check on the specific value
   or symbol carrying the finding over a check that a file exists.
4. **Record**, one node at a time:

   ```bash
   python tools/dag_update.py --action adopt --node-id H-204.4.24 \
     --adoption adopted \
     --artefact "path/to/Classifier.java" \
     --verification "grep -q 'channelFactor = 0.02' path/to/Classifier.java"
   ```

5. **Run the loop.** `reconcile.py` executes every predicate and reports what no longer holds.
   It exits non-zero on drift, so it can gate a merge or run on a schedule.
6. **Raise work** for each finding, against the owning artefact, per the AAW seam. The finding
   is the deliverable; the remedy is the work item.

## Quick reference

```bash
# Seed adoption blocks on a DAG that predates AAR 1.2.0
python .ai-assisted-research/tools/reconcile.py --dag research/hypothesis-dag.yaml --migrate

# Run the loop
python .ai-assisted-research/tools/reconcile.py --dag research/hypothesis-dag.yaml --cwd .

# Record a verdict
python .ai-assisted-research/tools/dag_update.py --action adopt --node-id H-001 \
  --adoption adopted --artefact "src/Thing.java" \
  --verification "grep -q 'thing = 0.02' src/Thing.java"
```

## Reporting

Finding kinds and their precedence are in
[references/finding-kinds.md](references/finding-kinds.md).

## Model leeway

The workflow is mandatory: two axes, demonstrate rather than assert, and report without
proposing.

The tools are a reference implementation. Find more rigorous ways to establish adoption if you
can, provided you adhere to the project's research principles and record a predicate that
someone else can run.

## Related skills

- `/aar-run-audit` checks whether the research is sound, which is the other axis.
