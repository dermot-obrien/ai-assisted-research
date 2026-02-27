# WI-001 Research Management System - AI Agent Addendum

> **Document Type**: AI Agent Addendum  
> **Parent Document**: [`scope.md`](scope.md)  
> **Audience**: AI Agents only (not for stakeholder distribution)  
> **Purpose**: Preserves intent-forming interactions, decision rationale, and agent instructions that supplement the published scope document.

---

## About This Document

The published scope document (`scope.md`) is the stakeholder-facing specification for this work item. This addendum provides AI agents with:

1. **Intent Formation History** - The original user instruction and how it evolved through dialogue
2. **Decision Rationale** - Why specific choices were made during scoping
3. **Agent Instructions** - Guidance for AI agents working on this work item

AI agents should read both documents together to fully understand the work item context.

---

## Intent Formation History

### Original User Instruction

The verbatim instruction that initiated this work item:

> I want to create a research management system. These are the constraints I want to deal with. Mainly I do research over long periods and often forget the strands.
>
> What I want to be able to do is use multiple agent systems like Gemini, Claude, Cursor, etc. over multiple sessions, whether online or at my terminal, and be able to consistently navigate my research and record where I'm at. How I would use this is to start off a particular topic with some intentions or outcomes I want to research. The first thing that an agent would do as part of this framework would be to go and find out all of the papers in the current state of the art and firstly create a baseline.
>
> What I want you to do is research all modern approaches to lineage of ideas. What I want to be able to do is target articles for both blogs and ARXIV. Here's how it generally works: an agent would pick up a topic from a hypothesis tree and would go and look at the research scope and go and do research and propose changes and propose alternatives and do work on the underlying work products. It would then create a blog-style article for that research segment, but also an ARXIV article, so that would be the main output. A next-level agent could go and pick that up if that's authorized, to go and make changes. Additive changes to the underlying code base are not anything destructive, but I want to do this using a taxonomy approach. I'm thinking of essentially it's more graph-structured and a tree structure, so you know the research would have a start research command, which would be like the start work command of the assisted work. It would do lots of requests. It would go into plan mode and query the user about intent and do a lot of proper scoping so that the full topic is captured.
>
> Now, they're just going to be really, really loose; it's going to be some area, but the window agent is in plan mode. It should be able to go and find out all out all of the state of the art, and particularly does this focus more on academic research, so it would be looking at the likes of ARXIV or anything else, not just general web researchers. This is quite focused on scientific research. It will go and, I think, that's a key first step, a central node of this graph, this linear ideal lineage tree or graph (I say graph, but it's probably more a tree). That's something to consider as part of this scoping exercise.
>
> You, Jim, and I, I want you to go into plan mode and query me and ask me specifics about this topic, because it is wide ranging. I also want to have a good system for maintaining that knowledge graph so that, no matter where I am in what system I'm using, I can have agents working on things and decide what the common mechanism is, whether that is gate or something else.

### Clarifying Questions & Answers

These questions were asked during scoping to refine requirements:

| # | Question | Answer | Rationale |
|---|----------|--------|-----------|
| 1 | How should this system integrate with the existing AI-Assisted Work (AAW) framework? | **Standalone System** | The user wants a separate, dedicated framework with its own conventions. |
| 2 | What is the preferred mechanism for maintaining the knowledge graph across agents and sessions? | **Provide recommendations (Accepted: File-based/Git)** | Git provides built-in lineage and versioning, and Markdown/YAML is readable by all agents. |
| 3 | What should be the primary model for the research lineage? | **Provide recommendations (Accepted: Graph (DAG) Structure)** | A DAG allows for both branching and merging research strands, which is common in complex research. |
| 4 | Beyond ARXIV, which specific academic sources or research tools should the agent prioritize? | **Provide recommendations (Accepted: Semantic Scholar API + Zotero)** | Semantic Scholar covers multiple academic databases and provides a high-quality API. |

### Synthesized Intent

Develop a **Standalone Research Management System** designed for tracking the **lineage of ideas** across long-term academic and blog-oriented research. The system will leverage a **Git-centric, file-based persistence model** (Markdown/YAML) and a **Directed Acyclic Graph (DAG)** lineage structure to ensure continuity across multiple agent systems (Gemini, Claude, Cursor) and sessions. Key workflows will include a `start-research` command for intent discovery and **SOTA (State of the Art)** baselining via APIs like Semantic Scholar.

---

## AI Agent Instructions

### Working with This Work Item

1. **Read both documents**: Always read `scope.md` first for the formal specification, then this addendum for context and rationale.
2. **Respect decision rationale**: Follow the accepted recommendations (Git-based, DAG, Semantic Scholar). Do not propose alternatives without explicit approval.
3. **Terminology consistency**: Use these terms consistently:
   - **Lineage of Ideas** (not "research history")
   - **SOTA Baseline** (State of the Art baseline)
   - **Additive Changes** (all changes must be non-destructive)
   - **Handoff Protocol** (for agent transitions)
4. **Scope boundaries**: 
   - Exclude any changes to the existing `aaw` system.
   - Focus on Agent/CLI accessibility over GUI.

### Key Concepts to Understand

| Concept | Definition | Key Point |
|---------|------------|-----------|
| **Lineage DAG** | A Directed Acyclic Graph tracking the evolution of research. | Allows branches and merges without cycles. |
| **SOTA Baseline** | The current state of scientific research for a given topic. | Must be established before new research starts. |
| **Additive Evolution** | Iterating on research without deleting previous findings. | Preserves history and avoids data loss. |

### Related Workspace Artifacts

- `change/work-items/` - Current location for shared work items in this workspace.

---

## Document History

| Date | Change | Author |
|------|--------|--------|
| 2026-02-28 | Initial addendum created from scoping session (Reset to WI-001) | AI Agent |
