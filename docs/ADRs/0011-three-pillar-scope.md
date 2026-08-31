# ADR-0011: Scope the build to three pillars, risk-ordered

**Status:** Accepted    
**Date:** 2026-08-30    
**Spec references:** §13

## Context

The full design comprises seven substantial subsystems: evidence graph with elicitation, pipeline keeper, composer with credits, two-pass execution, opportunity scoring, analyst with exploration, and interview preparation. Building all of them partially is the most likely failure mode — not a flawed premise, but an ambitious system where nothing is finished.

Scope also determines which risks are discovered late. Feature-ordered development builds the tractable parts first and encounters the hard ones with no time to respond. The hardest problem here — reliable server-side form fill against live third-party pages — is also the differentiator, so discovering it is infeasible in the final week would be unrecoverable.

## Decision

Three pillars ship. Everything else is stubbed, cut, or invisible plumbing.

| Pillar | Demonstrable claim |
|---|---|
| Two-pass apply | The form filled itself correctly on a live third-party ATS |
| Credits | Every line traces to a real source; the system refused to claim what it could not support |
| Analyst loop | Hypothesis, experiment, measured result, next hypothesis — one full turn |

Work is ordered by risk retired, not by feature area. Spikes A (form fill) and B (credits) run first and in that order, each with an explicit kill criterion. If A cannot be retired, the system reshapes around Pass 1 and the analyst — a decision taken at that gate rather than late.

No agent work begins until fixtures exist: ATS forms, a labeled mail corpus, an artifact-backed evidence seed, a non-engineer profile with no public artifacts, and an outcome backfill.

Cut outright and staying cut: interview dossier generation, web research on employer sponsorship, account creation and credential handling, any auto-submission path, additional ATS platforms, mobile client.

## Consequences

**Positive.** Each shipped pillar is complete enough to rely on rather than merely describe. The riskiest unknown is resolved first, while there is still room to respond to the answer.

**Negative.** The system is visibly narrower than the design it implements. Adjacent uses with genuine value — performance-review generation from the same evidence graph, interview preparation — are deliberately not built, and the temptation to add them is the exact pressure this record exists to resist.

**Fixture cost.** The non-engineer profile is not optional. Without it, the credits pillar cannot be shown to work for applicants without public repositories (ADR-0002), and that limitation would surface under questioning rather than under test.

## Alternatives considered

**Build all subsystems shallowly.** Rejected: produces a system where every component is demonstrable only in narration.

**Feature-ordered development.** Rejected: defers the hardest risk to the point where nothing can be done about it.

**Drop form fill and lead with credits and analysis.** Held as the contingency if Spike A fails, not chosen up front — form fill is the capability incumbents avoid, and abandoning it before testing forfeits the strongest position.
