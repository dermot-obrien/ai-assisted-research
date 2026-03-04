# /housekeep (Redirection)

Update dashboards, sync DAG statuses, and regenerate visuals.

## Protocol Redirection
This command is executed by the **Housekeeper Agent**. For detailed instructions and protocol, see:
- [**Housekeeper Agent Definition**](.ai-assisted-research/agents/housekeeper.md)

Key responsibilities include:
- Syncing DAG statuses and updating Mermaid visuals.
- **Regenerating `node-index.yaml`** — the precomputed actionable view of the DAG (ready/active/blocked nodes). This is the canonical index refresh point.
