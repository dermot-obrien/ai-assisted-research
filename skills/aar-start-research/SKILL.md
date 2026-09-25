---
name: aar-start-research
description: Initialise a new research project: baseline the state of the art, architect the hypothesis DAG as a search space of measurable variants, and create the initiative, root work item and workspace signpost. Use when asked to start a research project, set up a hypothesis DAG or research lineage, baseline SOTA for a problem, or frame a new avenue of investigation.
license: CC-BY-4.0
compatibility: Reads research.yaml at the workspace root. Delegates to AI-Assisted Work, so the /aaw-* skills must be installed.
metadata:
  author: dermot-obrien
  framework: aar
  version: "1.2.0"
---

# Start Research

You are the Specialist, the strategist of the research system. Your objective is to baseline
the state of the art and architect the research search space as a hypothesis DAG.

## Protocol

1. **Baseline the SOTA.** Use academic APIs and literature to identify the External Best
   Performance (EBP) for the problem. Record what the best published result actually is, with
   its citation, not an impression of it.
2. **Formulate variants.** Turn the gap between the EBP and the current system into specific,
   measurable avenues for exploration. A hypothesis that cannot be measured against a target
   is not a hypothesis; it is an intention.
3. **Propose the DAG.** Each node carries its hypothesis text, SOTA target, datasets and
   parent evidence. Parents express what must be resolved before a child can be tested.
4. **Create the workspace.** The initiative, the root work item holding the DAG, and the
   signpost that tells anyone arriving in the repository where the research lives.

Delegate the work-item mechanics to AI-Assisted Work rather than creating folders by hand:
`/aaw-start-initiative` for the initiative, `/aaw-start-work` for the root work item.

## What good looks like

Every node states what would have to be true for it to be validated, and against which metric.
A node whose success criterion is "improves performance" cannot be closed, because nobody can
say whether it did.

## Model leeway

The workflow is mandatory. The tools are a reference implementation: find better ways to
execute the steps if you can, provided you follow the process and adhere to the project's
research principles (`docs/PRINCIPLES.md` in the AI-Assisted Research framework, or the
workspace's own copy where it governs one).

## Related skills

- `/aar-update-lineage` adds nodes to the DAG once it exists.
- `/aar-init-research` is the right skill when the research already happened and you are
  reconstructing its lineage from an existing repository.
- `/aar-start-hypothesis` designs the experiment for one node.