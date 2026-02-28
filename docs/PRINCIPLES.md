# RMS Research Principles & Autonomy Guardrails

This document defines the foundational principles that guide autonomous agent behavior in the Research Management System. Agents are granted **maximum leeway** to innovate, provided they adhere to these core guardrails.

---

## 1. Metric Supremacy
Research is a search of a metric space. 
- **Guardrail**: Every hypothesis node MUST have a quantifiable performance target and actual result.
- **Leeway**: Agents may choose or invent any benchmarking methodology, provided it is rigorous and reproducible.

## 2. Lineage Continuity
The "Lineage of Ideas" is the primary product of the RMS.
- **Guardrail**: A subsequent agent (or human) must always be able to trace the "Why" and "How" of every research node.
- **Leeway**: Agents may use any narrative style or documentation format (Blog, ARXIV, or otherwise), provided the rationale is clear.

## 3. Additive Evolution
The research base grows; it does not shrink.
- **Guardrail**: All changes to the underlying work products and the research hub MUST be additive. Never delete previous findings or code without a clear "Discarded Node" record.
- **Leeway**: Agents are authorized to refactor, expand, or introduce new architectural patterns.

## 4. Workflow Supremacy (Process Integrity)
The RMS workflows (Initialization, Proposal, Execution, Audit, Synthesis) are mandatory and immutable.
- **Guardrail**: Agents MUST follow the defined process sequence and hit all Review Gates.
- **Leeway**: None for process. Agents must stick to the workflow to ensure cross-agent compatibility.

## 5. Intelligent Tooling (Tool-as-Accelerant)
Provided tools are reference implementations, not constraints.
- **Guardrail**: If a tool is bypassed or replaced, the agent must still produce the required output for that workflow stage (e.g., valid YAML, valid Markdown).
- **Leeway**: Agents are encouraged to use their advanced reasoning, call newer APIs, or develop their own utility scripts to execute a workflow step if they outperform the provided tools.

## 6. Baseline Anchoring (Standardized Comparison)
Every research domain MUST have validated baselines before hypothesis execution begins.
- **Guardrail**: No hypothesis node may be executed (moved to `in_progress`) until its domain has at least one baseline node with `status: validated` and `actual_performance` populated. Baselines use published SOTA models on standardized datasets with reproducible scripts.
- **Leeway**: Agents may choose any published SOTA model as the baseline, provided it is the current or recent best performer on the chosen benchmark and results are independently reproducible.
