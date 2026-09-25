---
name: aar-start-hypothesis
description: Design the experiment for one hypothesis node: check its readiness against the node index, extract its SOTA targets and parent evidence, and delegate to AAW start-work to create the work item blueprint, then move the node to framed. Use when asked to start, frame, scope or design a hypothesis or research node, or to plan an experiment before running it.
license: CC-BY-4.0
compatibility: Reads research.yaml at the workspace root. Delegates to AI-Assisted Work, so the /aaw-* skills must be installed.
metadata:
  author: dermot-obrien
  framework: aar
  version: "1.2.0"
---

# Start Hypothesis

The Research Design phase. It maps onto AAW `/aaw-start-work`: it takes a hypothesis node from
the research lineage and initialises a work item blueprint for exploring it.

Usage: `/aar-start-hypothesis {node_id}`

## Phase 1: Extract the research context

1. **Verify readiness, index first.** Read the node index per
   [references/node-selection.md](references/node-selection.md).
   - `{node_id}` in `ready`: proceed, its parents are resolved.
   - `{node_id}` in `blocked`: warn the user about the unresolved parents listed in
     `blocked_by` and confirm before proceeding.
   - Not found: the index is stale. Fall back to the full DAG.
2. **Load the node** from `hypothesis-dag.yaml`, or `hypothesis-tree.md` where that is still
   the source.
3. **Extract the metadata**: hypothesis text, SOTA targets, datasets, parent evidence.

## Phase 2: Delegate to AAW

Invoke `/aaw-start-work` with:

| Parameter | Value |
|-----------|-------|
| Work item title | `{node_id}-research-{short-topic}` |
| Source of truth | The hypothesis node text, verbatim |
| Intent | "Investigate {hypothesis}. Baseline SOTA, implement change, and quantify improvement." |
| Acceptance criteria | Derived from the node's SOTA targets and metric requirements |
| Research phase | Populate `research.md` from the node's evidence and key competitors |

Do not create work item folders or documents by hand. AAW owns that mechanism, and a
hand-rolled work item will not be found by the tools that expect one.

## Phase 3: Update the lineage

1. Record the generated `WI-{NNN}` in the DAG node's metadata.
2. Move the node status from `pending` to `framed`.

## Framing is archival

The point is to capture the experimental design while the idea is fresh. Even if
implementation never starts, the plan survives as a blueprint, and a blueprint someone can
read later is worth more than an intention nobody wrote down.

## Model leeway

The workflow is mandatory. The tools are a reference implementation: find better ways to
execute the steps if you can, provided you follow the process and adhere to the project's
research principles (`docs/PRINCIPLES.md` in the AI-Assisted Research framework, or the
workspace's own copy where it governs one).

## Related skills

- `/aar-progress-hypothesis` executes what this skill designs.
- `/aar-update-lineage` adds the node if it does not exist yet.