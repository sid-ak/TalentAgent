# ADR-0010: Target three ATS platforms; exclude prohibited automation

**Status:** Accepted    
**Date:** 2026-08-30    
**Spec references:** §1.3, §6.2, G5, §13.4

## Context

Two independent pressures bear on platform selection.

**Terms compliance.** Several major job platforms prohibit automated interaction. Building against them risks the user's account mid-search, which is a severe failure for a tool whose purpose is to protect that search.

**Maintenance cost.** Each supported platform requires a deterministic field map (ADR-0008) and fixtures. Support breadth trades directly against per-platform reliability, and the failure mode of thin support is a system that works on one platform and stutters on the others.

Greenhouse, Lever, and Ashby expose public job-board endpoints, are widely used among the target employer segment, and are largely account-optional or lightweight at the authentication step — which materially reduces the residual human cost established in ADR-0001.

## Decision

Three platforms are supported: Greenhouse, Lever, Ashby.

Platforms prohibiting automated interaction are excluded by design. The permitted-domain list is enforced at the network egress layer of the form worker, so a posting URL outside it fails before reaching application code — making the guardrail independent of model behavior.

Coverage of the remaining workflow does not depend on excluded platforms: the user's own inbox and calendar, user-supplied postings, and public board endpoints are sufficient.

If a platform cannot reach the 90% fixture-completion criterion, it is dropped rather than the criterion lowered.

## Consequences

**Positive.** No terms-of-service exposure and no account risk. Per-platform reliability is high enough to rely on. Eligibility data comes from public structured filings rather than scraping, which is both permitted and more defensible.

**Negative.** Workday is not supported. It represents a large share of enterprise applications and imposes per-employer account creation, which is exactly where ADR-0001's residual human cost is highest. An applicant whose search runs predominantly through Workday-style portals receives substantially less value. This is the design's clearest limitation and is stated rather than hedged.

**Future.** Adding an unauthenticated platform is a bounded unit of work — field map plus fixtures — but each addition carries ongoing maintenance as forms change. Adding an authenticated platform additionally requires the delegated-session mechanism recorded in Spec §15.1.

## Alternatives considered

**Broad platform support including prohibited ones.** Rejected: account risk to the user, and terms violation.

**Generic model-driven fill across any ATS.** Rejected: see ADR-0008; non-deterministic and untestable, and it does not remove the terms problem.

**Single platform.** Rejected: one platform is insufficient to demonstrate that the field-map approach generalizes.
