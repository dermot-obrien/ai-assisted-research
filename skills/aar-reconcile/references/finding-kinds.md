# Finding kinds

Report by kind, most consequential first.

| Kind | Meaning |
|---|---|
| `drift` | A predicate that used to hold no longer does |
| `validated_contradicted` | The system does what a validated node warns against |
| `validated_not_adopted` | Validated, nothing blocking it, and absent |
| `unverified_claim` | Claims adoption with no predicate to show it |
| `unknown_blocker` | `blocked_by` names a node that does not exist |
| `no_adoption_block` | Never assessed |

A predicate that cannot be executed is reported as `drift`, deliberately. A check you cannot
run is not a check that passed, and treating it as one is how a reconciliation loop quietly
stops meaning anything.

## Why the ordering matters

`drift` and `validated_contradicted` describe a system actively doing the wrong thing.
`validated_not_adopted` describes one merely missing an improvement. The first two cost
something now; the third is an opportunity. Reporting them in one undifferentiated list
invites triage by whoever reads it first.
