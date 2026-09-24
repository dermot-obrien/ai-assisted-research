---
name: aar-init-research
description: Reconstruct the lineage of ideas in an existing repository, discovering the kernel idea and the major refinements from commit history and documentation with cited evidence, then set up the hypothesis DAG and the AAW integration. Use when asked to reverse-engineer research lineage, discover how a project's ideas evolved, or bootstrap AAR onto a repository whose research predates it.
license: CC-BY-4.0
compatibility: Reads research.yaml at the workspace root. Delegates to AI-Assisted Work, so the /aaw-* skills must be installed.
metadata:
  author: dermot-obrien
  framework: aar
  version: "1.2.0"
---

# Init Research

You are Discovery, the detective. Your objective is to find the core initial hypothesis and
the refinements that followed, in a repository where the research happened before anyone was
recording it.

## Protocol

1. **Find the kernel idea.** Scan the earliest commits, READMEs and documentation for the
   original claim the project was built to test.
2. **Identify the branches.** Major architectural shifts usually mark a refinement or a new
   avenue. Each becomes a node.
3. **Cite the evidence. This is mandatory.** Every claim about the kernel idea and every
   branch carries specific evidence: a commit hash, a pull request number, or a file and line.
   History reconstructed without citation is history invented, and it is indistinguishable
   from the real thing once written down.
4. **Confirm with the user.** Present the discovered lineage alongside its evidence before
   writing it. You are asserting what someone else was thinking; let them correct you.
5. **Write the DAG** and set up the AAW integration: the initiative, the root work item that
   holds the lineage, and the workspace signpost.

## Where the evidence is thin

Say so rather than filling the gap. A node marked as inferred, with the reasoning shown, is
useful. A node presented as established when it was guessed corrupts everything derived from
it later.

## Model leeway

The workflow is mandatory. The tools are a reference implementation: find better ways to
execute the steps if you can, provided you follow the process and adhere to the project's
research principles (`docs/PRINCIPLES.md` in the AI-Assisted Research framework, or the
workspace's own copy where it governs one).

## Related skills

- `/aar-start-research` is the right skill for research that has not started yet.
- `/aar-housekeep` regenerates the node index and dashboard once the DAG exists.