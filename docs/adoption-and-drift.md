<!--
SPDX-FileCopyrightText: 2026 Dermot O'Brien
SPDX-License-Identifier: CC-BY-4.0
-->

# Adoption and Drift

**Status:** active · **Since:** AAR 1.2.0

A hypothesis has two independent states, and conflating them is how a research
record comes to misrepresent reality.

| Axis | Question | Field | Decided by |
|---|---|---|---|
| Epistemic | Is it true? | `status` | The research |
| Adoption | Is it live? | `adoption.state` | The implementation |

Before 1.2.0 the DAG modelled only the first. `status: validated` was therefore
read as "this is how the system works" when it only ever meant "this experiment
came out positive". Nothing in the record could express the difference, so a node
could sit at `validated` indefinitely while production did the opposite.

This mirrors the Continuous Reconciliation Standard in AI-Assisted Architecture,
which implements its principle that drift is the enemy. AAA reconciles the
catalogue against the running system; AAR reconciles the hypothesis DAG against
it. The vocabulary here is deliberately the same: gates, loops, drift, findings.

## The adoption block

```yaml
adoption:
  state: not_assessed
  artefact: null
  verification: null
  verified_on: null
  note: null
```

### States

| State | Meaning |
|---|---|
| `not_assessed` | Nobody has asked. The default for a new node. |
| `not_applicable` | The node makes no claim about a running system. Evaluation method, literature review, infrastructure. |
| `not_adopted` | Validated, nothing blocking it, and absent from the system. |
| `partial` | Present, but not at the setting the research established. |
| `adopted` | The system does what the node validated. |
| `contradicted` | The system does the thing the node warns against. |

`contradicted` is deliberately distinct from `not_adopted`. Absence is an
omission; contradiction is the system acting against a finding, and the two
warrant different responses.

### Why a predicate, not a path

`artefact` alone cannot prove adoption, because a file can exist and do the wrong
thing. `verification` holds a shell command that exits zero when the claim still
holds:

```yaml
adoption:
  state: adopted
  artefact: "src/main/java/.../OnnxGifsClassifier.java"
  verification: "grep -q 'channelFactor = 0.02' src/main/java/.../OnnxGifsClassifier.java"
  verified_on: 2026-09-23
```

This is what makes drift detectable rather than merely recordable. A node whose
predicate starts failing has drifted, and the reconciler finds it on a schedule
instead of a human noticing months later.

A node claiming `adopted` or `partial` without a `verification` is reported as
unverified. Claiming adoption is not the same as demonstrating it, and the
framework should not let the two look alike.

Predicates run through the platform shell, so keep them portable or put the
logic in a script the predicate calls. A predicate that cannot execute is
reported as drift, deliberately: a check you cannot run is not a check that
passed.

## Preconditions

```yaml
blocked_by: [H-204.3.3.2]
```

Absent-and-blocked and absent-and-unexplained are different states, and without
this they are indistinguishable without reading prose. A node with `state:
not_adopted` and a non-empty `blocked_by` is correctly absent. One with an empty
`blocked_by` is a gap.

Closing the blocking node also surfaces the blocked one as newly deployable,
which is a scheduling signal the DAG could not previously give.

## Contest and supersession

```yaml
contested_by: [H-204.7.7]
status: contested
```

Before 1.2.0 a challenge had nowhere to attach. A later node could undermine an
earlier one's evidence and the earlier node would stay `validated`, reading as
settled to anyone who arrived at it.

`contested` is a non-terminal status. A node leaves it by the challenge being
resolved in either direction, not by time passing.

## Gate and loop

Following AAA's division:

- **Gates** run at merge. Schema validation rejects a node with `state: adopted`
  and no `verification`, or a `blocked_by` pointing at an unknown id.
- **Loops** run on a schedule. `reconcile.py` executes every predicate and
  reports what no longer holds.

Gates stop you recording drift. Loops stop drift accumulating from everything
gates cannot see, which is most of it, because the DAG and the system change
independently.

## What this does not do

It does not prevent divergence. An implementation can still ignore a validated
finding. What changes is the delay between that happening and somebody knowing:
from indefinite, to one scheduled run.

It also does not interact with research validity. A node built on leaked features
with a green predicate is a faithfully implemented wrong answer. The two axes are
orthogonal and the framework models both without joining them, deliberately.

## Migrating an existing DAG

`reconcile.py --migrate` adds a default `adoption` block to every node that lacks
one, at `state: not_assessed`. Nothing is inferred, because inferring adoption is
the judgement the tool exists to make explicit.

Triage after migration is the real work, and it is the point: every node sitting
at `not_assessed` is a question nobody has asked yet.
