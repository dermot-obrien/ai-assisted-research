# /cascade

Analyse how a breakthrough cascades through the hypothesis DAG.

**Usage**: `/cascade {node_id}`

**Trigger**: Automatically invoked by `/log-experiment --breakthrough` or `/sync-research-result` when a node status changes to `validated` or `ineffective`.

**Agent**: See [`agents/cascade.md`](../../../../agents/cascade.md) for the full protocol.

**What it does**:
1. Identifies the assumption change from the breakthrough
2. Scans all DAG nodes for affected premises
3. Classifies effects: strengthened, weakened, contradicted, unblocked, elevated, superseded
4. Updates `breakthroughs.yaml` with cascade effects
5. Updates `findings-graph.yaml` with relationship edges
6. Updates node priorities in `node-index.yaml`
