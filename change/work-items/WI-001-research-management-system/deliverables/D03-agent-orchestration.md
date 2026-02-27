# Deliverable: WI-001-D03 Agent Orchestration

> Activity: WI-001-A3 Multi-Agent Orchestration
> Status: Complete

## Overview

This deliverable implements the logic and orchestration for the multi-agent ecosystem (Specialist, Worker, Auditor).

## 1. Specialist Agent (The "Planner")

The Specialist agent is responsible for "Hypothesis Generation" and "Avenue Discovery."

### Role Logic
1. **Context Acquisition**: Reads the root `hypothesis-dag.yaml` and any completed `metadata.yaml` files.
2. **Analysis**: Evaluates current performance results and identifies gaps or potential variants in the solution space.
3. **Proposal**: Generates new nodes for the DAG, including hypothesized performance gains and dependencies.
4. **Update**: Appends new nodes to `hypothesis-dag.yaml` in a `pending` status for Worker pickup.

### Specialist Tool (`tools/dag_update.py`)
A utility for agents to safely update the `hypothesis-dag.yaml` file without corrupting the structure.

## 2. Worker Agent (The "Optimizer")

The Worker agent is the "Engine" of the system, responsible for implementation, benchmarking, and synthesis.

### Role Logic
1. **Node Selection**: Identifies an unblocked, `pending` node in `hypothesis-dag.yaml`.
2. **Setup**: 
   - Creates a new Git branch: `research/{node_id}-{topic}`.
   - Initializes `metadata.yaml` with its ID, `role`, and `parent_performance`.
3. **Implementation**: Changes the underlying codebase (additive) to test the hypothesis.
4. **Benchmarking**: Runs the predefined test suite and records `actual_performance`.
5. **Synthesis**:
   - Generates a **Blog Narrative** (narrative/storytelling style).
   - Generates an **ARXIV Formal Paper** (formal/academic style).
6. **Handoff**: Updates `metadata.yaml` to `status: awaiting_review` and sets `next_role: auditor`.

### Worker Tool (`tools/branch_manager.py`)
A utility for agents to safely create branches, initialize `metadata.yaml`, and push changes.

## 3. Auditor Agent (The "Validator")

The Auditor agent is the "Gatekeeper" responsible for rigorous verification of results and claims.

### Role Logic
1. **Selection**: Picks a research branch with `status: awaiting_review` and `next_role: auditor`.
2. **Verification**:
   - Re-runs the benchmark suite to verify `actual_performance`.
   - Checks code changes for artifacts or non-additive modifications.
   - Validates the consistency between performance data and claims in the blog/ARXIV papers.
3. **Recommendation**:
   - If performance is improved and verified: Recommend merging to `main`.
   - If performance is not improved: Recommend discarding the node but preserving the research (lineage).
4. **Handoff**: Marks the node as `Ready for Human Review` in `metadata.yaml`.

### Auditor Tool (`tools/audit_verify.py`)
A utility for agents to perform automated checks on the performance and code quality of a research branch.
