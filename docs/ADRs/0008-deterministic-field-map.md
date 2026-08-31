# ADR-0008: Deterministic field map with narrow model fallback

**Status:** Accepted    
**Date:** 2026-08-30    
**Spec references:** §5.5, §13.3

## Context

Server-side form fill is the system's highest-risk component (R1) and its most distinctive capability. The obvious implementation is a single agentic loop: give a model browser control and the application context, and let it complete the form.

That design couples two failure modes that are better kept apart. Deciding *what to say* is a reasoning problem over evidence. Deciding *where to put it* is a mechanical problem over a DOM. A single loop fails at both simultaneously, is non-deterministic in a live third-party page, and cannot be tested without hitting real endpoints.

It is also the hardest option to trust. A browser loop that stutters unpredictably undermines confidence in precisely the load-bearing component.

## Decision

Two passes, separated by the kind of problem each solves.

**Pass 1 — Compose.** Model-driven, offline, testable against fixtures. Produces credited bullets, credited screening answers, and gaps from the evidence graph. No browser involved.

**Pass 2 — Execute.** Deterministic-first. Enumerate fields; resolve each against a per-platform field map from stable identifiers to package keys; fall back to the model only for fields the map does not cover — in practice, custom screening questions. Upload materials, capture the completed form, halt.

Fallback frequency is measured. The deterministic map is expected to carry the standard fields; a rising fallback rate is a signal that a platform's form has changed.

## Consequences

**Positive.** Failure modes are independent and separately measurable. Pass 1 is fully testable without network access. Pass 2's reliability is a per-platform number rather than an impression.

**Negative.** Field maps are per-platform and must be maintained. An ATS DOM change breaks the map, which is why misses are recorded per field and the run halts with a partial capture rather than guessing.

**Scope coupling.** Maintaining maps is the practical reason platform support is narrow (ADR-0010).

## Alternatives considered

**Single agentic browser loop.** Rejected: couples failure modes, non-deterministic on live pages, untestable offline.

**Pure deterministic fill with no model.** Rejected: custom screening questions are the highest-value fields and cannot be mapped.

**Client-side extension fill.** Rejected: moves execution to the user's machine and forfeits the autonomous-preparation claim.
