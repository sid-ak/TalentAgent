# ADR-0004: Reserve an exploration budget in analyst assignment

**Status:** Accepted    
**Date:** 2026-08-30    
**Spec references:** §7.2, §12

## Context

ADR-0003 prevents a low prior from excluding an opportunity, but ranking alone does not prevent the underlying pathology. If a segment is consistently ranked last, it receives little traffic, generates few outcomes, and its estimate never updates. The system's initial conclusion — potentially drawn from eight samples and several confounds — becomes permanent by inaction.

This is the exploit-only failure of a bandit problem. It is particularly damaging here because the tool's stated purpose is to replace superstition about job searching with measurement. A system that hardens its own early estimates manufactures exactly the superstition it exists to remove, and does so with more authority than the user's own guesswork.

The analyst already registers assignment rules that steer subsequent applications. Those rules were greedy.

## Decision

Assignment is not purely greedy. With probability ε, an application is assigned to a segment drawn from those in `INSUFFICIENT_EVIDENCE` or with the lowest priors; otherwise it goes to the current best segment.

Three details are load-bearing:

- **ε is declared and reported**, not an internal constant. The user can see what fraction of effort is spent on testing rather than exploiting.
- **Exploration targets interval width, not low mean.** Information is located in uncertainty. A confidently poor segment yields less than an unsampled one.
- **Exploration assignments are labeled** in the outcome log and excluded from exploit-side effect estimates, so deliberate sampling does not contaminate the measurements it exists to enable.

Findings retired by expiry (ADR-0009) become eligible for exploration, which is the mechanism by which stale conclusions are retested rather than inherited.

## Consequences

**Positive.** Every conclusion the analyst reaches remains contestable by the system itself. Combined with expiry, no finding can become permanent through neglect. Exploration budget spend becomes a reportable health metric: a loop that has stopped exploring has stopped learning.

**Negative.** A fixed share of applications is deliberately assigned to segments currently believed suboptimal. This is a real cost paid in the user's actual job search, not a simulation, and it must be disclosed rather than buried.

**Tuning.** ε is not derived in this build. It is set conservatively and reported; deriving it from the observed variance across segments is future work.

## Alternatives considered

**Pure exploitation.** Rejected: freezes estimates, which is the failure this record exists to prevent.

**Full Thompson sampling.** Deferred: better principled, but harder to explain to the user whose applications are being assigned, and the sample sizes here do not justify the additional machinery.

**Manual retest prompts.** Rejected: depends on user discipline, which the system's own design principles reject as an intake mechanism.
