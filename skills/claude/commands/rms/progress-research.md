# /progress-research

Resume work on the current research strand. Convenience command that looks up the next ready node from the node index and delegates to `/progress-hypothesis`.

**Usage**: `/progress-research` (no arguments — auto-selects from golden path or ready queue)

## Instructions

1. Read `research.yaml` to locate `node_index_path`.
2. Read `node-index.yaml` and select the first `ready` node (prefer `golden_path: true` nodes).
3. If the node has a work item, delegate to `/progress-hypothesis {WI_id} {node_id}`.
4. If the node has no work item, delegate to `/start-hypothesis {node_id}` first.

**Agent**: See `.ai-assisted-research/agents/worker.md` for the full Worker protocol.
