# ADR-0002: Graded attestation classes instead of artifact-only provenance

**Status:** Accepted    
**Date:** 2026-08-30    
**Spec references:** §3.2, §3.3, §3.4, §3.5, G1

## Context

The original evidence graph admitted only artifact-backed accomplishments, with a hard invariant that every claim reference at least one commit, pull request, or document. This made provenance structural rather than aspirational and directly countered the category's central failure: models fabricating qualifications to match a job description.

The invariant does not survive contact with real applicants. It describes software engineers whose work is public and whose access to it persists. It excludes the majority case: accomplishments held in private repositories the applicant no longer has access to, internal systems they cannot reach, and work that produced no artifact at all — a migration led, a decision made, a team unblocked.

Admitting user-asserted evidence introduces circularity. If "the user typed it" counts as evidence, a credit certifies nothing, and the graph launders a self-assertion into the appearance of rigor. That is worse than making no provenance claim, because it presents as verification while performing none.

The resolution is to state the guarantee precisely. The guarantee was never that a third party verified the claim. It was that the model did not originate it. That boundary — user-originated versus model-originated — is unaffected by whether an artifact exists.

## Decision

Provenance is graded, not binary. Every credit carries one of four attestation classes:

| Class | Origin | Admissible |
|---|---|---|
| `verifiable` | User's work, third-party inspectable | Yes |
| `corroborated` | User's work, privately held, producible on request | Yes |
| `attested` | User's dated statement, no artifact | Yes, labeled |
| `derived` | Proposed by the model | No — quarantined until user confirmation |

A `Statement` node type is introduced alongside `Artifact`. The `derived` quarantine is the load-bearing invariant: a model may propose an accomplishment, never originate one that reaches an employer.

`statement.raw` retains the user's verbatim text, stored separately from any generated line derived from it, so generated phrasing cannot drift from the assertion without the drift being visible on inspection.

Coverage is reported per class and never as a single scalar.

## Consequences

**Positive.** The provenance pillar generalizes beyond applicants with public repositories. The system can label its own weaker evidence rather than hiding it, which is a stronger trust signal than uniform confidence.

**Negative.** Click-through provenance is strongest on `verifiable` credits; `attested` credits resolve only to the user's own words. Coverage metrics become harder to state in one number, correctly.

**Boundary.** Truthfulness of an `attested` claim is the user's responsibility. It is made in their words, under their name, on their application. The system does not adjudicate it and must not claim to.

## Alternatives considered

**Artifact-only.** Rejected: works for one applicant profile and fails for most.

**Unclassified user input.** Rejected: produces credits that certify nothing.

**Model-generated evidence with a confidence score.** Rejected: confidence is not provenance, and it reintroduces exactly the fabrication failure the pillar exists to prevent.
