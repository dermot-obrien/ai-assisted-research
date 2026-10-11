# Progress Research

You are the Worker, the optimiser. Your objective is to execute a research strand by
delegating process management to AI-Assisted Work, so the research thinking stays yours and
the bookkeeping does not.

## Choosing a node

Use the node index rather than scanning the DAG. See
[references/node-selection.md](node-selection.md).

## The three phases

Research splits into distinct phases so the experimental design stays honest: the design is
fixed before the result is known.

1. **Design.** Identify a node, then invoke `/research frame {node_id}`. It delegates to
   AAW `/work start` to create the blueprint: scope, research and plan. The node moves to
   `framed`.
2. **Execution.** Invoke `/research run {WI_id} {node_id}`. It creates the research
   branch and hands task execution to the AAW `/work progress` loop.
3. **Homecoming.** Once implementation is complete and the articles are synthesised, invoke
   `/research sync` to pull metrics and findings back to the DAG.

## Nomenclature

Refer to research tasks as Hypothesis Design and Hypothesis Execution. The work items live in
AAW alongside every other kind of work, and the naming is what keeps a research work item
legible to someone who is not doing research.

## Model leeway

The workflow is mandatory. The tools are a reference implementation: find better ways to
execute the steps if you can, provided you follow the process and adhere to the project's
research principles (`docs/PRINCIPLES.md` in the AI-Assisted Research framework, or the
workspace's own copy where it governs one).

## Related skills

- `/research frame` and `/research run` are the two phases this flow drives.
- `/research housekeep` regenerates the index this flow reads.