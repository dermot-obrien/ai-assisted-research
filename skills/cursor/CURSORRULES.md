# Research Management System (RMS) - Cursor Rules (Redirection)

Cursor agents should adopt specialized RMS personas based on the current task.

## Persona Redirections

- For Project Initialization: Adhere to [**Discovery Agent Protocol**](../../agents/discovery.md).
- For DAG Maintenance: Adhere to [**Specialist Agent Protocol**](../../agents/specialist.md).
- For Feature Implementation & Writing: Adhere to [**Worker Agent Protocol**](../../agents/worker.md).
- For Audit: Adhere to [**Auditor Agent Protocol**](../../agents/auditor.md).
- For Dashboard Maintenance: Adhere to [**Housekeeper Agent Protocol**](../../agents/housekeeper.md).

## Key Entry Point
Agents should always start by reading `research.yaml` from the workspace root to discover the initiative, root work item, and DAG path.

## Process & Guidance
Refer to the [**User Guide**](../../docs/user-guide.md) for step-by-step instructions and [**Research Principles**](../../docs/PRINCIPLES.md) for autonomy guardrails.
