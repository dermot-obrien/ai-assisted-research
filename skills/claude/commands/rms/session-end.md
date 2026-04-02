# /session-end

End a research session with a summary report and handoff.

**Usage**: `/session-end`

**Agent**: See [`agents/session.md`](../../../../agents/session.md) for the full protocol.

**What it does**:
1. Generates session report YAML (experiments, nodes updated, breakthroughs, recommendations)
2. Saves to `sessions/session-{datetime}.yaml`
3. Regenerates dashboard
4. Commits session report
5. Prints handoff summary for the next session/agent
