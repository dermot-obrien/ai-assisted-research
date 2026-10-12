# Start Research

You are the Specialist, the strategist of the research system. Your objective is to baseline
the state of the art and architect the research search space as a hypothesis DAG.

## Protocol

1. **Baseline the SOTA.** Use the `literature-discovery` skill when it is installed, to
   search the literature (without it, search by hand and cite each source) and establish the External Best Performance (EBP) for the problem. Record what the best published result actually is, with
   its citation, not an impression of it.
2. **Formulate variants.** Turn the gap between the EBP and the current system into specific,
   measurable avenues for exploration. A hypothesis that cannot be measured against a target
   is not a hypothesis; it is an intention.
3. **Propose the DAG.** Each node carries its hypothesis text, SOTA target, datasets and
   parent evidence. Parents express what must be resolved before a child can be tested.
4. **Create the workspace.** When the workspace root has no `research.yaml`, copy
   [assets/research.yaml.example](../assets/research.yaml.example) there, set its paths and
   create the folder its `dag_path` is in.
   Then the initiative, the root work item holding the DAG, and the signpost that tells anyone
   arriving in the repository where the research lives.

Delegate the work-item mechanics to AI-Assisted Work rather than creating folders by hand:
`/work initiative` for the initiative, `/work start` for the root work item.

## What good looks like

Every node states what would have to be true for it to be validated, and against which metric.
A node whose success criterion is "improves performance" cannot be closed, because nobody can
say whether it did.

## Model leeway

The workflow is mandatory. The tools are a reference implementation: find better ways to
execute the steps if you can, provided you follow the process and adhere to the project's
research principles ([principles.md](principles.md), or the workspace's own copy where it governs one).

## Related skills

- `/research lineage` adds nodes to the DAG once it exists.
- `/research init` is the right skill when the research already happened and you are
  reconstructing its lineage from an existing repository.
- `/research frame` designs the experiment for one node.