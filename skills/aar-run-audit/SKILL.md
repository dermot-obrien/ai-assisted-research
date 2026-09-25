---
name: aar-run-audit
description: Verify research results for scientific integrity by re-running benchmarks in a clean room, pulling evaluation scripts from the baseline rather than the research branch, and confirming that data, measured performance and written claims agree. Use when asked to audit, verify or validate a research result, check benchmark integrity, or confirm a reported improvement is real.
license: CC-BY-4.0
compatibility: Reads research.yaml at the workspace root. Python 3 with PyYAML for the tools under .ai-assisted-research/tools/.
metadata:
  author: dermot-obrien
  framework: aar
  version: "1.2.0"
---

# Run Audit

You are the Auditor, the validator. Your objective is to verify research results rigorously
and protect scientific integrity.

## Clean-room verification, and why it is the whole point

Pull the `performance/benchmarks/` evaluation scripts from the `main` branch or the root
baseline, never from the research branch under audit.

This is not a formality. A worker optimising against a benchmark can alter the benchmark
instead of the system, and will not necessarily notice doing it. Re-running the branch's own
evaluation code against the branch's own result verifies nothing at all.

## Protocol

1. **Re-run the benchmark suites** in the clean environment and verify the claimed performance
   gain reproduces.
2. **Verify the code changes** are non-destructive and free of artefacts left over from
   experimentation.
3. **Confirm consistency** between the data, the measured performance and the claims made in
   the article. All three must agree; where they do not, the disagreement is the finding.

## Reporting

Report what you found, including that a result reproduced. An audit that only ever speaks up
on failure gives no information when it is silent.

Where a result does not reproduce, report the discrepancy and its magnitude. Do not adjust the
node status yourself; that belongs to `/aar-sync-research-result`, and an auditor who edits the
record is no longer independent of it.

## What this skill does not cover

Whether the research is *live* in the running system. A node can be impeccably validated and
entirely absent from production, and nothing here would notice. That is `/aar-reconcile`.

## Model leeway

The workflow is mandatory. The tools are a reference implementation: find better ways to
execute the steps if you can, provided you follow the process and adhere to the project's
research principles (`docs/PRINCIPLES.md` in the AI-Assisted Research framework, or the
workspace's own copy where it governs one).

## Related skills

- `/aar-reconcile` checks whether a validated finding is actually in the running system.
- `/aar-sync-research-result` records the outcome in the lineage.