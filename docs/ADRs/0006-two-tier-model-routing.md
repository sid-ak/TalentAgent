# ADR-0006: Two-tier model routing with a small-model gate

**Status:** Accepted    
**Date:** 2026-08-30    
**Spec references:** §9.2, §12

## Context

The inbound mail path processes every message arriving in the user's inbox. The overwhelming majority are not job-related. Routing all of them to a frontier model is straightforward to build and indefensible to operate: the cost of the highest-volume path would be set by the model needed for its rarest and hardest cases.

The work in that path also divides cleanly. Deciding whether a message concerns a job application is a classification with a stable label set. Deciding what a recruiter's ambiguous reply implies about application state is a judgment requiring context.

## Decision

Two tiers, with the boundary placed so that the small model decides whether the large model is needed.

| Tier | Model | Role |
|---|---|---|
| 1 | Gemini Flash-Lite | First-pass classification of every inbound message; posting-relevance filtering |
| 2 | Gemini Flash | State reasoning, requirement-to-evidence mapping, constrained composition, hypothesis formation |

Tier-down rate — the share of events fully resolved at tier 1 — is a reported metric, not an implementation detail.

Thread attribution follows the same principle without involving a model at all: resolution is attempted deterministically first (thread ID, ATS reference, employer domain) and reaches tier 2 only on failure.

## Consequences

**Positive.** The cost of the highest-volume path is set by its typical case rather than its hardest. The architecture can be operated continuously, including during dormant periods between searches, which the evidence graph's value depends on.

**Negative.** Two model integrations, two prompt surfaces, two sets of failure modes. A tier-1 false negative silently drops a job-related message, which is a harder failure to detect than a false positive.

**Measurement.** Tier-1 precision is a Spike D success criterion (≥95%) precisely because its errors are silent.

## Alternatives considered

**Frontier model for everything.** Rejected on cost, and it forecloses continuous operation.

**Rules-based pre-filter.** Rejected: sender and subject heuristics are brittle across ATS vendors and miss the messages that matter most.

**Single model with cheap prompting.** Rejected: does not address volume, and conflates two tasks with different accuracy requirements.

## Amendment (2026-08-30)

Two changes under the zero-budget constraint (ADR-0012), neither of which alters the decision.

**Tier assignment is now Flash-Lite and Flash rather than Gemma and Pro.** Pro-class models left the Gemini free tier on 1 April 2026, and Vertex AI has no free tier at all. Flash-Lite carries 1,000 free requests per day against Flash's 250, so the tier boundary now buys daily quota headroom rather than only cost.

**The rationale strengthens.** Tiering was previously a cost argument; it is now the mechanism that keeps the highest-volume path inside a hard daily ceiling. Tier-down rate is correspondingly promoted from a reported metric to an operational constraint (Architecture §8).

**Gemma becomes the fallback rather than the default.** A small self-hosted Gemma classifier running in the Actions runner would remove the mail path from the API entirely. It is not the initial choice — an API call is simpler and the Flash-Lite allowance is expected to suffice — but it is the first move if tier-1 volume approaches the ceiling.
