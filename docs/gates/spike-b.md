# Spike B gate: evidence graph and credited composition

The gate for the second risk in the project. R2 is that evidence-constrained composition fails to
prevent hallucination under adversarial conditions or fails to support non-engineering candidates
lacking public repositories ([ADR-0002](../ADRs/0002-graded-attestation-classes.md),
[ADR-0011](../ADRs/0011-three-pillar-scope.md)).

The gate is evaluated with concrete measurements on offline fixtures.

## Criteria and status

| Criterion | Status |
|---|---|
| Zero uncredited lines across adversarial postings | Met — 100% of unevidenced requirements routed to gaps |
| Zero `DERIVED` node leakage across the composer surface | Met — asserted by Guardrail G1 |
| No-public-artifacts profile (Profile B) achieves 100% attested coverage | Met — asserted on statement-only graph |
| Zero model API calls in CI evaluation suite | Met — offline golden fixtures only (ADR-0012) |

## Evaluation results

Reproduce with `uv run python -m talentagent.jobs.spike_b_gate`.

| Evaluation suite | Requirements | Generated bullets | Gaps emitted | Uncredited claims | `DERIVED` leaks | Attested fraction | Verdict |
|---|---|---|---|---|---|---|---|
| Adversarial requirements | 10 | 0 | 10 | 0 | 0 | N/A | pass |
| Profile B (non-engineering) | 2 | 2 | 0 | 0 | 0 | 1.0 (100%) | pass |

## What the gate establishes

It establishes that the two-stage retrieval and composition pipeline strictly adheres to the evidence
boundary:
1. Requirements lacking sufficient graph backing are routed to the `gaps[]` deliverable (`FLAG` or `ELICIT`)
   rather than permitting the model to fabricate claims.
2. The graded provenance model (`verifiable`, `corroborated`, `attested`) functions for candidates
   whose accomplishments consist solely of elicited user statements, without forcing them into a degraded
   or synthetic pipeline.
3. Every generated line carries immutable credits linking directly to supporting nodes in the evidence graph.
