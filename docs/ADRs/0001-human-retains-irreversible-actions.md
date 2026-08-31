# ADR-0001: Human retains irreversible and identity-asserting actions

**Status:** Accepted    
**Date:** 2026-08-30    
**Spec references:** §1.4, §5.5, §9.1, G3

## Context

The category's dominant product is the volume bot: an agent that submits applications end to end. That design hands a machine the irreversible action, produces no learning signal (untargeted applications generate uninformative outcomes), and creates account-suspension risk on platforms that prohibit automated interaction.

A competing pressure exists. Autonomous server-side execution is the system's most technically distinctive capability, and stopping short of submission appears to weaken it. The question is where exactly the boundary belongs.

Examining the workflow's time budget resolves it. Preparation — eligibility assessment, evidence mapping, composition, form fill — accounts for the large majority of per-application effort. Account creation, authentication, bot challenges, and the submit action account for seconds and recur rarely, where they arise at all.

Those four residual actions share a property: each asserts identity. Authenticating asserts that the actor is the account holder. A bot challenge asserts personhood. Submission asserts that the claims are the user's own. Automating identity assertion is impersonation regardless of intent, and in the case of screening answers it is the specific behavior that has made the category distrusted.

## Decision

The system performs all preparation, tracking, and analysis autonomously. It does not perform account creation, authentication, bot-challenge solving, submission, or offer acceptance and decline.

`submit_application` is classified `human-only` and is absent from every agent tool registry. The capability is additionally withheld at the IAM layer from the service that drives the form, so the exclusion does not depend on application code being correct.

Authentication does not arise on the target platforms, which accept applications without a candidate account (ADR-0010). The system holds no ATS credential or session.

## Consequences

**Positive.** Anti-bot challenges fire at submission, where a human is already present, so the human boundary and the platform's own boundary coincide rather than conflict. The review step is not pure overhead — it is where the user inspects credits and gaps, which is the product's value. Account risk is eliminated.

**Negative.** On platforms requiring per-employer account creation, the residual human cost is materially higher and the savings claim weakens. This is the strongest available objection to the design and is not fully answered; it is bounded by platform scope (ADR-0010).

**Structural.** The autonomy claim rests on the inbound and analysis paths, which contain no human at all, rather than on the apply path.

## Alternatives considered

**Full auto-submission.** Rejected: hands a machine an irreversible action, degrades outcome data quality, and creates account risk.

**Human approval on every field.** Rejected: eliminates the time saving that justifies the system.

**Agent solves bot challenges.** Rejected outright. Circumventing personhood checks is out of scope on both ethical and terms-compliance grounds.
