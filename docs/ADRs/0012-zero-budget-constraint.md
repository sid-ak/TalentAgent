# ADR-0012: Build within a zero-budget, card-free constraint

**Status:** Accepted    
**Date:** 2026-08-30    
**Spec references:** §9.3, §11, §13.2, Architecture §2, §8, §10

## Context

The build has no budget and no billing account, and none will be created. This is a hard constraint, not a preference, and it was surfaced after the architecture had been specified against Cloud Run, Pub/Sub, Cloud Scheduler, and BigQuery.

Three findings determine what remains possible:

**Cloud Run, Pub/Sub, and Cloud Scheduler require a linked billing account** even to consume the always-free tier. Linking is a verification step rather than a charge, but there is no path to using these services without a payment instrument.

**Some Google services are reachable with a standard account and cannot bill at all.** Firestore on the Firebase Spark plan provides 1 GiB and 50k reads / 20k writes per day, and when a quota is exhausted the product refuses requests rather than charging. The Gemini API free tier provides Flash at 250 requests per day and Flash-Lite at 1,000, with Pro-class models removed from the free tier on 1 April 2026. Google Apps Script runs on a standard account with native Gmail access.

**BigQuery's sandbox is unsuitable regardless.** It forbids DML and streaming ingestion and expires data after 60 days, which is incompatible with a durable append-only log.

Two further options were considered and rejected as unreliable. The $300 free trial is per person and requires a payment method. Education credits are genuinely card-free and redeemable with a school-issued address, but are granted through an institution's participation, generally require faculty sponsorship, and take up to three weeks to process — worth pursuing in parallel, but not something to design around.

## Decision

The system is built entirely on tiers that require no payment instrument.

| Function | Choice |
|---|---|
| Event ingress and mail-path compute | Google Apps Script time-driven trigger; hourly weekdays, 6-hourly otherwise |
| Long-running and scheduled compute | GitHub Actions on a public repository; Chromium preinstalled |
| Durable state | Firestore on the Firebase Spark plan |
| Immutable outcome log | Append-only Firestore collection, enforced by security rule |
| Web surface | Firebase Hosting, static, with Firebase Auth |
| Run artifacts | GitHub Actions artifacts, 90-day retention |
| Inference | Gemini API free tier: Flash-Lite for tier 1, Flash for tier 2 |

BigQuery is removed from the design entirely. At single-user scale the outcome log is a few hundred rows, and segment analysis is an in-process operation.

Two practices become mandatory rather than advisory:

- **Golden-fixture model responses.** Model outputs are recorded once and replayed; the test suite makes zero API calls. Development, not operation, is what exhausts a 250-per-day quota.
- **Tier-1 routing discipline.** Classification runs on Flash-Lite, which carries four times the daily allowance of Flash.

## Consequences

**Positive.** The Spark plan cannot generate a bill, so the failure mode of a runaway loop is refusal rather than cost — a stronger guarantee than a budget alert on a paid account. GitHub Actions is a better fit for the form worker than anticipated: runners ship with Chromium, so no container build is needed, and every run leaves logs and retained artifacts, which is an audit trail the design already values. Removing BigQuery eliminates a service without weakening any guarantee.

**Negative, and load-bearing.** Three real regressions:

1. **The ingress is no longer push.** A scheduled Apps Script trigger replaces Gmail `watch()` → Pub/Sub. ADR-0005 rejected polling on the grounds that cron pretending to be an event path misrepresents the architecture; that objection stands and is answered by stating the mechanism plainly rather than by claiming push. See ADR-0005 as revised.
2. **Write ownership drops from IAM to security rules.** Without Cloud Run there are no per-component service accounts. The single-writer invariant becomes a Firestore rules configuration rather than an infrastructure property.
3. **Egress control drops to the application layer.** Guardrail G5's permitted-domain list moves from a VPC egress policy into the fetch wrapper, where it is enforced by code and tests rather than by the network.

**Operational ceiling.** The Gemini Flash daily quota is the binding constraint on the whole system, at roughly 2× headroom against estimated use (Architecture §8) — the tightest margin anywhere in the design.

## Alternatives considered

**Attach a card and use always-free tier.** Rejected by constraint. It would have kept the entire original architecture at $0, since this workload sits far inside every free-tier ceiling.

**New account for the $300 trial.** Rejected. The trial requires a payment method regardless, and farming trials across accounts violates the terms.

**Run compute on the user's own machine.** Rejected. The autonomy claim requires work to happen while nobody is present, which a laptop cannot guarantee, and it forfeits any hosted-project evidence.

**Non-Google free compute for the workers.** Considered and left available as a fallback, but GitHub Actions covers the scheduled and dispatched cases without adding a fourth vendor.

## Reversal

This decision is reversible without touching agent contracts, schemas, or coordination semantics. The migration path — ingress, jobs, write ownership, egress control, artifacts — is tabulated in Architecture §10. Specifying topology separately from contracts is what makes that true.
