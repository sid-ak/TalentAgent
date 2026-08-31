# ADR-0003: Eligibility may gate; priors may only rank

**Status:** Accepted    
**Date:** 2026-08-30    
**Spec references:** §6.1, §6.3, §6.4, G4

## Context

An earlier formulation scored opportunities on "eligibility and measured outcome history" as though these were two instances of one kind of signal. They are not, and treating them alike produces a specific harm.

Eligibility — whether an employer sponsors a visa, for instance — is a fact about the world. It is externally sourced from public filings, independently verifiable, and true regardless of the applicant's actions. If sponsorship is required and an employer does not sponsor, the application cannot succeed, and reporting that before an hour is spent is the correct behavior.

Outcome history is an estimate about the applicant, and it fails in four independent ways:

- **Small n.** Zero replies across eight applications has a posterior interval of roughly 0 to 20 percent. The maximum-likelihood rate of zero measures nothing.
- **Confounding.** Channel is not randomly assigned. Portal applications correlate with larger employers, weaker fit, and absent sponsorship. A channel effect silently absorbs all of them.
- **Non-stationarity.** The evidence graph has grown, materials have changed, the market has moved. An outcome from six months ago describes a different candidate.
- **Self-confirmation.** A down-ranked segment receives no further traffic, collects no data, and retains its initial estimate permanently.

Under the merged formulation, an applicant could be quietly steered away from an entire channel on the strength of eight samples, with no mechanism to ever revise that.

## Decision

Two score types with distinct powers, never merged into a single value.

`eligibility` may gate — it can remove an opportunity from output. `prior` may rank only — it adjusts order and can never exclude.

The prior record enforces honesty structurally: intervals rather than point estimates; a third state `INSUFFICIENT_EVIDENCE` distinct from `WEAK`; declared confounds; recency decay by half-life.

`may_exclude` is `false` on every prior record. The field exists to make the invariant explicit and assertable in tests; it is not configurable.

## Consequences

**Positive.** No opportunity is suppressed for a reason the user cannot inspect and that the system cannot justify externally. "No data here" and "this looks weak" render differently, which is the distinction users actually need.

**Negative.** Ranking output is longer and less decisive than a filtered list. Some users will prefer a shorter list, and this design refuses to produce one on self-derived evidence.

**Enforcement.** Ranking-layer check plus a test asserting no prior record can exclude. Guardrail G4.

## Alternatives considered

**Single blended fit score.** Rejected: merges a verifiable fact with a noisy estimate and hides which one is acting.

**Allow priors to gate above a confidence threshold.** Rejected: any threshold reachable on job-search sample sizes is reachable by noise, and gating is precisely what makes the estimate unrevisable.

**Report priors but never use them.** Rejected: discards real signal and leaves the user to do the ranking manually.
