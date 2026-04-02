# /session-start

Begin a research session with a full briefing.

**Usage**: `/session-start`

**Agent**: See [`agents/session.md`](../../../../agents/session.md) for the full protocol.

**What it does**:
1. Reads `research.yaml` for all artifact paths
2. Regenerates dashboard
3. Prints session briefing: node counts, golden path, recent breakthroughs, pending cascades, papers in progress
4. Asks: "Continue with the golden path, or explore a different direction?"

**This should be the FIRST command in every research session.**
