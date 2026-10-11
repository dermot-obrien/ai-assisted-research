# Update Lineage

You are the Specialist, the strategist. Your objective here is to extend the research search
space: add or revise nodes in the hypothesis DAG.

## Protocol

1. **Re-baseline where needed.** If the External Best Performance has moved since the DAG was
   written, say so. A target fixed against a stale SOTA produces a validated node that is
   already behind.
2. **Formulate the variant.** Specific and measurable: what change, against what metric, with
   what target. "Try a bigger model" is not a node.
3. **Place it in the DAG.** Its parents are the nodes that must be resolved before it can be
   tested, not merely the ones that came before it chronologically. Getting this wrong is what
   makes the `ready` list lie.
4. **Record the evidence**: the citation, the dataset, the parent result it builds on.
5. **Regenerate the node index** so the new node appears in `ready` or `blocked`, per
   `/research housekeep`. A node that is not in the index is invisible to everything that reads it.

## A node that cannot be measured

Push back rather than recording it. The DAG's value is that every node can be closed with a
verdict. One that cannot be closed sits in `pending` forever and quietly makes the `ready`
list less useful.

## Model leeway

The workflow is mandatory. The tools are a reference implementation: find better ways to
execute the steps if you can, provided you follow the process and adhere to the project's
research principles (`docs/PRINCIPLES.md` in the AI-Assisted Research framework, or the
workspace's own copy where it governs one).

## Related skills

- `/research start` creates the DAG this flow extends.
- `/research frame` designs the experiment for a node.
- `/research housekeep` regenerates the index after a change.