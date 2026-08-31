# ADR-0009: Findings carry expiry; outcomes decay

**Status:** Accepted    
**Date:** 2026-08-30    
**Spec references:** §6.3, §7.1, §7.2, §12

## Context

The analyst produces findings — measured statements about which channels, variants, and segments perform better. Without an expiry rule, findings accumulate and continue to influence ranking indefinitely.

Two properties of this domain make that unsafe. Sample sizes are small, so a finding often rests on a dozen observations and a directional effect. And the subject of the measurement is not stationary: the evidence graph grows, materials change, the applicant's seniority shifts, and the market moves. A finding from six months ago describes a different candidate applying into different conditions.

An unexpiring finding therefore converts a weak measurement into a permanent assumption, with the system's authority attached. That is the same failure as the superstition the tool exists to replace, made worse by appearing quantitative.

## Decision

Findings are maintained rather than accumulated.

- Every finding carries `expires_after_days`. On expiry it ceases to influence ranking and returns to the hypothesis queue for retest.
- Every finding carries `n` and an explicit strength qualifier. Unresolved confounds are recorded on the finding.
- Prior computation applies recency decay by half-life, so older outcomes count less rather than equally.
- Expired findings become eligible for the exploration budget (ADR-0004), which is the mechanism by which they are actually retested rather than merely deactivated.

Findings expired versus retested is a reported metric.

## Consequences

**Positive.** No conclusion becomes permanent through neglect. The reported strength of a claim degrades honestly with its age. Combined with ADR-0004, the system continuously re-earns its own beliefs.

**Negative.** Effective sample sizes are smaller than raw counts, and in a domain already short of data this makes findings harder to establish. Some genuinely stable effects will be retested unnecessarily.

**Presentation.** A finding reported with `n=12` and a `low-n, directional` qualifier reads as rigor; the same effect size reported bare overstates what was measured. The qualifier is a required schema field, not a caveat added at display time.

## Alternatives considered

**Permanent findings.** Rejected: manufactures superstition with quantitative authority.

**Uniform weighting of all outcomes.** Rejected: treats a two-year-old application as evidence about the current applicant.

**Manual invalidation by the user.** Rejected: depends on the user noticing staleness, which is the thing they cannot do unaided and the reason the analyst exists.
