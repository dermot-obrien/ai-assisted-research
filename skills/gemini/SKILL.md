# Research Management System (RMS) - Gemini Skill

This skill enables Gemini agents to track the lineage of ideas and conduct performance-driven research.

## Activation
Copy the contents of this folder to your project's `.gemini/skills/rms/` directory.

## Core Commands (Redirections)

- **/init-research**: Reconstruct lineage in existing projects. (Ref: [`../../agents/discovery.md`](../../agents/discovery.md))
- **/start-research**: Begin a new research project. (Ref: [`../../agents/specialist.md`](../../agents/specialist.md))
- **/progress-research**: Resume work or start the next available node. (Ref: [`../../agents/worker.md`](../../agents/worker.md))
- **/update-lineage**: Add/update DAG nodes. (Ref: [`../../agents/specialist.md`](../../agents/specialist.md))
- **/research-hypothesis**: Begin research on a specific hypothesis node. (Ref: [`../../agents/research-hypothesis.md`](../../agents/research-hypothesis.md))
- **/execute-strand**: _(deprecated, use /research-hypothesis)_ (Ref: [`../../agents/worker.md`](../../agents/worker.md))
- **/run-audit**: Verify results. (Ref: [`../../agents/auditor.md`](../../agents/auditor.md))
- **/sync-research-result**: Synchronize AAW findings back to the RMS DAG. (Ref: [`sync-research-result.md`](sync-research-result.md))
- **/housekeep**: Update dashboards. (Ref: [`../../agents/housekeeper.md`](../../agents/housekeeper.md))

## Agent Instructions
When executing RMS commands, always adhere to the foundational principles in [`../../docs/PRINCIPLES.md`](../../docs/PRINCIPLES.md).
