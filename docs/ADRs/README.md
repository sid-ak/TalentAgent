# Architecture Decision Records

Records of decisions that shaped TalentAgent's design and would be expensive or destabilizing to reverse. Each records the context at the time of the decision, what was decided, and what it costs.

Format: context · decision · consequences · alternatives considered. A record is written when a decision constrains future work, not when it merely describes it.

| ADR | Title | Status |
|---|---|---|
| [0001](./0001-human-retains-irreversible-actions.md) | Human retains irreversible and identity-asserting actions | Accepted |
| [0002](./0002-graded-attestation-classes.md) | Graded attestation classes instead of artifact-only provenance | Accepted |
| [0003](./0003-eligibility-gates-priors-rank.md) | Eligibility may gate; priors may only rank | Accepted |
| [0004](./0004-exploration-budget.md) | Reserve an exploration budget in analyst assignment | Accepted |
| [0005](./0005-derived-pipeline-state.md) | Derive application state from the inbox | Amended |
| [0006](./0006-two-tier-model-routing.md) | Two-tier model routing with a small-model gate | Amended |
| [0007](./0007-coordination-through-state.md) | Coordinate through durable state, not agent-to-agent calls | Accepted |
| [0008](./0008-deterministic-field-map.md) | Deterministic field map with narrow model fallback | Accepted |
| [0009](./0009-findings-expire.md) | Findings carry expiry; outcomes decay | Accepted |
| [0010](./0010-platform-scope.md) | Target three ATS platforms; exclude prohibited automation | Accepted |
| [0011](./0011-three-pillar-scope.md) | Scope the build to three pillars, risk-ordered | Accepted |
| [0012](./0012-zero-budget-constraint.md) | Build within a zero-budget, card-free constraint | Accepted |

## Status values

| Status | Meaning |
|---|---|
| Proposed | Under consideration; not yet binding |
| Accepted | In force; the specification reflects it |
| Superseded | Replaced by a later ADR, which is named in this record |
| Amended | Still in force, with a dated amendment recording what a later constraint changed |
| Deprecated | No longer applies; not replaced |
