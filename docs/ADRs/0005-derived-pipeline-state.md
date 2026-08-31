# ADR-0005: Derive application state from the inbox

**Status:** Accepted    
**Date:** 2026-08-30    
**Spec references:** §4.1, §4.3, §8.1

## Context

Existing application trackers are manual. They are accurate on the day they are set up and degrade from there, because their value depends on discipline the user does not sustain past roughly week six of a search. An abandoned tracker is worse than no tracker: it presents stale state with the authority of a record.

The authoritative state of an application already exists elsewhere. Confirmations, rejections, scheduling requests, and recruiter contact all arrive in the user's inbox, and interviews land on the user's calendar. Any state the user types is a second, lower-quality copy of information the system could read directly.

Silence is also information, and it is the case no event can carry. Twelve days without contact after a recruiter screen is the most common outcome in a search and produces no message to classify.

## Decision

Application state is derived from observed inbox and calendar events and is never hand-entered.

`GHOSTED` is time-derived: entered when a per-state silence threshold elapses. It is the only transition with no triggering message, and it is what makes staleness detection automatic rather than a reminder the user must act on.

Transitions are monotonic except by explicit correction, so a low-confidence classification cannot walk state backwards. Below a confidence threshold, a transition is proposed rather than applied and surfaces for review.

## Consequences

**Positive.** There is no app to keep current, and state cannot drift from reality. Follow-up drafting becomes automatic because the condition triggering it is computed rather than remembered.

**Negative.** The system requires inbox access, which is a significant permission for a tool the user may not open for weeks at a time. Applications submitted outside the tracked inbox are invisible until a reply arrives.

**Dependency.** Correctness rests on classification precision and thread attribution (Spec §13.3, Spike D). A wrongly advanced application is a visible failure of the autonomy claim, which is why attribution is resolved deterministically where possible and the confidence gate exists.

## Alternatives considered

**Manual tracker with reminders.** Rejected: reminders are a discipline tax, not a solution to a discipline problem.

**Browser extension capturing submissions.** Rejected: covers only the submit moment and none of the six weeks after it, which is where the cost actually is.

**Polling on a schedule.** Rejected at the time: cron pretending to be an event path adds latency and misrepresents the system's architecture.

## Amendment (2026-08-30)

The push mechanism this record assumed — Gmail `watch()` → Pub/Sub → an always-on worker — is unavailable under ADR-0012. Ingress is now a Google Apps Script time-driven trigger: hourly during weekday working hours, every six hours overnight and at weekends.

The decision this ADR records is unaffected: state remains **derived from observed inbox and calendar events, never hand-entered**, and `GHOSTED` remains time-derived. What changes is only how the observation is delivered.

The original objection to polling is not withdrawn, but it was aimed at the wrong target. The objection was to cron *masquerading* as an event path. The cadence here is set by the workflow: recruiter correspondence moves over half a day to several days, so an hour of latency on a weekday is immaterial. It is polling, described as polling.

An earlier revision set the cadence at one minute, which was chosen to stay close to push rather than to meet any requirement. It was also infeasible: 1,440 runs a day would have consumed most of the Apps Script daily runtime allowance polling an empty inbox. Widening the interval additionally allows tier-1 triage to classify a batch in one call rather than one call per message.

The idempotency requirement becomes stronger, not weaker: overlapping or missed runs are handled by a `lastHistoryId` cursor in addition to the per-message key. True push semantics are restored by the first row of the migration table in Architecture §10.
