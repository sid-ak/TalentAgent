# Spike A gate: two-pass apply

The gate for the highest-risk work in the project. R1 is that server-side ATS fill is unreliable on
live forms, and it is addressed first because if it cannot be retired the system reshapes around
Pass 1 and the analyst — a decision worth taking early, while there is still room to respond to it
([ADR-0011](../ADRs/0011-three-pillar-scope.md)).

The gate is passed with numbers, and it is allowed to fail. A platform that cannot reach 90% field
completion on fixtures is dropped. Lowering the criterion is not one of the options.

## Criteria and status

| Criterion | Status |
|---|---|
| ≥90% field completion on fixtures, per platform | Met — see the table below |
| One clean end-to-end run against a live posting, per platform | Not yet run — see [Outstanding](#outstanding) |
| Zero submissions from any non-human path, asserted in tests | Met — asserted across all twelve fixtures |

## Completion, measured

Reproduce with `uv run python -m talentagent.jobs.spike_a_gate`. The figures are read from the same
run captures a human reviews, so the reported number and the reviewed number cannot drift apart.

| Platform | Fixtures | Completion | Deterministic | Filled | By fallback | Unfilled | Declined | Verdict |
|---|---|---|---|---|---|---|---|---|
| ashby | 4 | 100.0% | 75.0% | 20 | 5 | 0 | 0 | pass |
| greenhouse | 4 | 100.0% | 70.4% | 27 | 8 | 0 | 4 | pass |
| lever | 4 | 100.0% | 75.0% | 20 | 5 | 0 | 0 | pass |

No platform is dropped.

### Reading the table

Completion is the share of fillable fields that ended up holding a value, whether the deterministic
field map put it there or the bounded fallback did. Both are Pass 2 doing its job.

Two columns are excluded from that denominator, and only two. Declined fields are the voluntary
demographic questions the Greenhouse map refuses on purpose: nothing in the evidence graph answers
them, the applicant may decline entirely, and an agent filling them would assert something about the
user that the user did not say. Counting them as failures would push towards filling them. Fields
still hidden behind an unanswered conditional are excluded too, since they are not yet part of the
form.

The deterministic column is the more diagnostic number and is not a gate. It is the share the field
map handled with no model involved. Watch for it falling while completion holds steady: that means a
platform changed its DOM and the fallback is quietly papering over it, which costs quota and turns a
deterministic fill into a guessed one.

## What the number does and does not establish

It establishes that the maps cover every standard field on all three platforms, that employer-authored
questions are correctly identified as unmappable rather than guessed at, that conditional fields are
filled after the answer that reveals them, and that a DOM change halts with a diagnosable partial
capture rather than continuing on best effort.

It does not establish that the maps survive contact with a live page. The fixtures are structural
reproductions authored against each platform's observable naming conventions, not captures of real
postings ([`tests/fixtures/ats/CAPTURE.md`](https://github.com/sid-ak/TalentAgent/blob/main/tests/fixtures/ats/CAPTURE.md)).
They are faithful to what a field map keys on, which is what the resolver is tested against, but
they cannot surprise us the way a real form can. That is exactly what the live runs are for, and
until those are done this gate is partially met rather than met.

## Outstanding

One criterion remains, and it needs a person rather than CI: one clean end-to-end run against a live
posting per platform, with the resulting artifact retained as the evidence.

Running it: dispatch the `form-worker` workflow with a real posting URL on each platform. The run
fills the form, captures it, and halts. A human then reviews the capture and, if they choose to
apply, submits it themselves — the worker has no code path that could.

It is carried out in Phase 5 rather than Phase 1, as
[#18](https://github.com/sid-ak/TalentAgent/issues/18). Phase 5 builds the `workflow_dispatch`
bridge from the review UI to the form worker, so the runs go through the same path a user would use
rather than a one-off dispatch, and the Definition of Done run records the artifacts as its evidence
for the first pillar claim. Phase 1 closed on what it could settle in CI; this gate stays open until
the runs exist.

When those three artifacts exist, record their run identifiers here, note the deterministic share
alongside the completion figure — a live page filling mostly by fallback means the map has drifted
from the real DOM even where completion holds — and mark the criterion met.
