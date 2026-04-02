# RMS Research Principles & Autonomy Guardrails

This document defines the foundational principles that guide autonomous agent behavior in the Research Management System. Agents are granted **maximum leeway** to innovate, provided they adhere to these core guardrails.

---

## 1. Metric Supremacy
Research is a search of a metric space. 
- **Guardrail**: Every hypothesis node MUST have a quantifiable performance target and actual result.
- **Leeway**: Agents may choose or invent any benchmarking methodology, provided it is rigorous and reproducible.

## 2. Lineage Continuity
The "Lineage of Ideas" is the primary product of the RMS.
- **Guardrail**: A subsequent agent (or human) must always be able to trace the "Why" and "How" of every research node. Every publishable finding must have a clear lineage back through the exploration chain to the foundational hypothesis (and ultimately to the core ideas the system is built on).
- **Leeway**: Agents may use any narrative style or documentation format (Blog, ARXIV, or otherwise), provided the rationale is clear.

## 3. Activity-Driven Exploration Within Nodes
Within a hypothesis node, research proceeds through a **chain of activities**, each driven by findings from the previous one.
- **Guardrail**: Every activity MUST produce a documented **finding** — a conclusion drawn from the work done. That finding SHOULD prompt the next activity (documented via a `prompted_by` field linking back to the prior finding). This creates a traceable exploration lineage within each node.
- **Structure**: Activity → Tasks → Finding → Next Activity (prompted by finding) → ...
- **Progress tracking**: Each activity in `progress.yaml` MUST include:
  - `finding`: The conclusion or result of the activity (what was learned)
  - `prompted_by`: What prior finding or observation motivated this activity
- **Purpose**: When a finding is publishable, the complete chain of "we tried X, learned Y, which led us to try Z" must be reconstructable from the activity records.

## 4. One Fundamental Change Per Node
Each hypothesis node represents **one fundamental theoretical direction or change to the solution**.
- **Guardrail**: Within a node, only **refinements** of that fundamental idea are permitted. Activities within a node explore, validate, and refine the node's core hypothesis — they do not introduce new theoretical directions.
- **Critical Rule**: If an activity's finding suggests a fundamentally different approach (not a refinement of the current hypothesis), that MUST become a **new hypothesis node**, not a continuation within the current node. The finding should be recorded, and a new node created with the current finding as its motivation.
- **Example**: Node 6.2 tests "LTSF models on irregular data." Finding that TSLib is structurally biased (A4) is a refinement. But if A4 had concluded "we need a completely different evaluation framework based on temporal attention," that would warrant a new node (e.g., 6.2.1 or 6.5).

## 5. Additive Evolution
The research base grows; it does not shrink.
- **Guardrail**: All changes to the underlying work products and the research hub MUST be additive. Never delete previous findings or code without a clear "Discarded Node" record.
- **Leeway**: Agents are authorized to refactor, expand, or introduce new architectural patterns.

## 6. Workflow Supremacy (Process Integrity)
The RMS workflows (Initialization, Proposal, Framing, Execution, Audit, Synthesis) are mandatory and immutable.
- **Guardrail**: Agents MUST use the `/start-hypothesis` command to design research and the `/progress-hypothesis` command to execute it. The loop is finalized with `/sync-research-result`.
- **Unified Hierarchy**: All research execution occurs within the standard AAW `change/work-items/` directory. Research work items MUST be identified by a `-research-` suffix in their title (e.g., `WI-NNN-research-topic`).
- **Process Sequence**: Agents must follow the defined process sequence and hit all Review Gates.
- **Leeway**: None for the core process loop (RMS -> AAW -> RMS). Agents must stick to the workflow to ensure cross-agent and cross-session compatibility.

## 7. Intelligent Tooling (Tool-as-Accelerant)
Provided tools are reference implementations, not constraints.
- **Guardrail**: If a tool is bypassed or replaced, the agent must still produce the required output for that workflow stage (e.g., valid YAML, valid Markdown, and the updated DAG node).
- **Leeway**: Agents are encouraged to use their advanced reasoning, call newer APIs, or develop their own utility scripts to execute a workflow step if they outperform the provided tools.

## 8. Experiments are First-Class (v1.2.0)
Research proceeds through experiments — the atomic unit of empirical work.
- **Guardrail**: Every experiment MUST be logged in `experiment-log.jsonl` with a hypothesis, metric, and result. Use `/log-experiment` to ensure the DAG, node index, and dashboard stay in sync. No experiment should be "lost" between sessions.
- **Structure**: Experiment -> Hypothesis (one sentence) -> Metric -> Result -> Verdict (improved/not improved/failed)
- **Leeway**: The agent may batch experiments and log them after a series, but each experiment must be individually recorded.

## 9. Breakthroughs Cascade (v1.2.0)
A breakthrough is a finding that changes the assumptions underlying other nodes.
- **Guardrail**: When a node moves to `validated` or `ineffective`, or when an experiment is marked as a breakthrough, the agent MUST run cascade analysis (`/cascade`). This identifies nodes whose premises have changed and updates their priorities.
- **Critical Rule**: Over-identify rather than under-identify. It is better to flag a node for re-evaluation that doesn't need it than to miss one that does.
- **Leeway**: The agent uses reasoning to identify non-obvious connections — keyword matching alone is insufficient.

## 10. Session Continuity (v1.2.0)
Research happens across sessions with gaps. Continuity must be preserved.
- **Guardrail**: Every session SHOULD begin with `/session-start` (briefing) and end with `/session-end` (report + handoff). The dashboard must be the primary interface for understanding research state.
- **Purpose**: A new agent (or the same human after a break) must be able to understand the full research state in under 60 seconds by reading the session briefing and viewing the dashboard.
- **Leeway**: The exact format of briefing and report may vary, but the content — what was done, what was found, what's next — must always be present.
