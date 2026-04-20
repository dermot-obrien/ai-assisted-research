# /housekeep (Redirection)

Regenerate the node index and refresh the research dashboard.

## Protocol Redirection
This command is executed by the **Housekeeper Agent**. For detailed instructions and protocol, see:
- [**Housekeeper Agent Definition**](.ai-assisted-research/agents/housekeeper.md)

Key responsibilities include:
- **Regenerating `node-index.yaml`** — the precomputed actionable view of the DAG (ready/active/blocked nodes). Run via `.ai-assisted-research/tools/generate_node_index.py`. This is the canonical index refresh point.
- **Rebuilding the dashboard** — run `.ai-assisted-research/tools/generate_dashboard.py` to regenerate the interactive HTML from the current DAG and experiment logs.
