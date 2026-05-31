# AAW Inquiry Seam — Work Classification ↔ Hypothesis

This document defines how the Research Management System (RMS / **AAR**) connects to the
[AI-Assisted Work](https://github.com/dermot-obrien/ai-assisted-work) **work-classification
standard** (`work-classification.md`). It is the contract that lets one vocabulary flow
across both frameworks without drift.

## The seam in one line

> **An AAW `inquiry` *is* an AAR hypothesis.** Uncertain work — "we don't yet know what to
> do" — is research, not delivery.

AAW triage has four classes (chore · change · intervention · inquiry). The first three are
delivery; the fourth, **inquiry**, is the seam into AAR. Anything classified `inquiry` is
handed to RMS to be framed, investigated, and concluded — and its conclusion is **re-triaged
back into AAW** as delivery work (or closed as a lesson).

## Inbound: an inquiry becomes a hypothesis

When AAW triage classifies a unit of work as `inquiry`, it hands off to RMS:

```
AAW triage → INQUIRY → AAR /start-hypothesis {node}   (frames the hypothesis)
                       AAR /progress-hypothesis        (runs the experiment)
                       AAR /sync-research-result        (records the metric/finding)
```

The hypothesis enters the RMS lifecycle and moves through the standard node statuses:
`pending → framed → in_progress → {partially_tested | contested} → {validated | ineffective} → completed`.

The originating intent (the AAW capture) becomes the hypothesis's framing; the inquiry is
now governed entirely by RMS principles (Metric Supremacy, Lineage Continuity, …) until it
concludes.

## Outbound: a conclusion re-triages into AAW

Research does not "deliver" — it **decides whether to deliver**. On conclusion, the outcome
re-enters AAW triage as a delivery class, or closes as a recorded lesson:

| RMS conclusion (node status) | Re-triage into AAW |
|------------------------------|--------------------|
| **validated** (go ahead, metric beats SOTA) | → a delivery item — usually an **intervention** (or a **change** if local), to implement the proven approach. Branch + version bump follow AAW's class rules. |
| **ineffective** (no improvement) | → **close as a lesson.** No delivery. The negative result is the deliverable (recorded in the DAG + findings). |
| **contested** (conflicting evidence) | → stay an **inquiry** (more research) or scope a smaller follow-up hypothesis. |
| **partially_tested** | → keep researching, or carve out the validated portion as a delivery item and leave the rest as an open inquiry. |

This is AAW's *promotion / re-triage* rule applied across the seam: classification is
provisional and cheap to revise. A validated hypothesis **spawns** a typed work item; an
ineffective one costs only the research, and the lesson is preserved.

## Decisions produced during research → AAA

A research strand often produces an architectural **decision** (e.g. "adopt approach X").
That decision is a deliverable that seams to **AI-Assisted Architecture (AAA)** as a
Decision Record (ADR / `DR-NNN`) — see AAA's work seam. RMS records the *finding*; AAA
records the *decision*; AAW delivers the *change*.

## Vocabulary alignment (no drift)

| Concept | AAW | AAR (RMS) |
|---------|-----|-----------|
| uncertain work | class `inquiry` | a hypothesis node |
| "investigate it" | route to AAR | `/start-hypothesis` |
| "proven, do it" | re-triage → intervention/change | node `validated` |
| "doesn't work" | close as lesson | node `ineffective` |
| traceability | work item ↔ commit ↔ version | hypothesis DAG lineage |

RMS owns the *research lifecycle*; AAW owns the *class definitions and the delivery
lifecycle*. The seam is `inquiry ↔ hypothesis` in, `conclusion → re-triage` out.

See AAW's `packages/skills/work-management/work-classification.md` for the full taxonomy.
