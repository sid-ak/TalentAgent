# ADR-0007: Coordinate through durable state, not agent-to-agent calls

**Status:** Accepted    
**Date:** 2026-08-30    
**Spec references:** §2.1, §2.2, §7.3, §8.6, §11

## Context

Five specialist agents must cooperate: triage, pipeline, evidence, composer, analyst. The conventional approach is direct delegation — one agent invokes another and awaits a result.

Direct delegation produces three problems at this scale. Failures compound along the call chain and become difficult to attribute. A step cannot be replayed without re-running everything upstream of it. And any two agents that can write the same field will eventually race on it, producing a value with no single responsible author.

The system also spans three trigger classes with different latency and durability characteristics — push events, scheduled jobs, and user intents — which do not compose cleanly under synchronous call semantics.

## Decision

Agents do not call one another. All coordination is by typed events and durable state.

**Single-writer invariant.** Exactly one agent owns each field. Cross-agent influence is expressed as an event or as state another agent reads. Any unexpected value therefore has exactly one suspect.

**The one deliberate influence path.** The analyst does not act on applications. It writes an assignment rule that the composer reads on the next apply. The learning loop closes through Firestore, not through a call.

**Idempotency.** Event delivery is at-least-once, so every event-driven transition is keyed on `evidence_message_id` and reprocessing is a no-op.

**Immutable history.** State is mutable; the outcome log is not. Corrections append. A later state correction cannot retroactively alter a reported finding.

## Consequences

**Positive.** Every step is independently testable against fixtures and replayable in isolation. Write ownership maps directly onto enforceable storage rules rather than convention. Debugging localizes to one agent.

**Negative.** Indirection. Tracing one logical workflow requires reading state transitions rather than a call stack, and end-to-end latency is higher than a direct call would give. Eventual consistency between agents must be reasoned about explicitly.

**Enforcement.** Firestore security rules keyed to a per-component identity claim, mirroring the exclusive-write column of the agent roster. Under the zero-budget constraint this is a rules configuration rather than an IAM property (ADR-0012); the invariant is unchanged, its enforcement is weaker, and Architecture §10 records how it is restored.

## Alternatives considered

**Orchestrator agent delegating to specialists.** Rejected: concentrates failure in one component and makes replay of a single step impossible.

**Shared mutable state with no ownership rules.** Rejected: races, and no way to attribute a bad value.

**Message passing between agents without durable state.** Rejected: no replay, and no audit trail for a system whose central claim is traceability.
