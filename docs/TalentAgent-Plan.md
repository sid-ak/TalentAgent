# TalentAgent Implementation Plan

The build broken into six phases. Each phase is a GitHub milestone, each has one epic issue holding
its task checklist, and each ends at a gate that can be passed or failed rather than at a feeling of
completeness.

This document is the bridge between the [specification](./TalentAgent-Spec.md), which says what the
system must do, and the issue tracker, which says what is being done next. It does not restate
either — for a contract read the spec, for a rationale read the relevant [ADR](./ADRs/README.md).

---

## Table of Contents

1. [How the phases are ordered](#1-how-the-phases-are-ordered)
2. [Phase 0: Foundations, fixtures, and the guardrail harness](#2-phase-0-foundations-fixtures-and-the-guardrail-harness)
3. [Phase 1: Two-pass apply, deterministic execution](#3-phase-1-two-pass-apply-deterministic-execution)
4. [Phase 2: Evidence graph and credited composition](#4-phase-2-evidence-graph-and-credited-composition)
5. [Phase 2.5: Interactive demo and review surface](#5-phase-25-interactive-demo-and-review-surface)
6. [Phase 3: The autonomous inbound pipeline](#6-phase-3-the-autonomous-inbound-pipeline)
7. [Phase 4: Opportunity scoring and the analyst loop](#7-phase-4-opportunity-scoring-and-the-analyst-loop)
8. [Phase 5: Production deployment and acceptance](#8-phase-5-production-deployment-and-acceptance)
9. [Risk coverage](#9-risk-coverage)
10. [Definition of Done coverage](#10-definition-of-done-coverage)

---

## 1. How the phases are ordered

Ordering is by risk retired, not by feature area. The reasoning is recorded in
[ADR-0011](./ADRs/0011-three-pillar-scope.md); the short version is that feature-ordered development
builds the tractable parts first and meets the hard ones with no time left to respond.

Two risks would reshape the system if they could not be retired, so they are addressed first and in
this order:

- R1 — server-side ATS fill is unreliable on live forms. Phase 1. If this cannot be retired, the
  system reshapes around Pass 1 and the analyst, and that decision is taken at the Phase 1 gate
  rather than in the final week.
- R2 — generation fabricates where evidence is absent. Phase 2. This is the guarantee the product
  is built on, so it is proven before anything is layered on top of it.

Everything in Phase 0 is a precondition. No agent work begins until the fixtures that agent is
measured against exist (Spec §13.2), because a system whose tests hit live models and live forms is
neither deterministic nor affordable under the quota ceiling in
[ADR-0012](./ADRs/0012-zero-budget-constraint.md).

What that rule requires is that a corpus precedes its consumer, not that every corpus precedes
everything. Phase 0 therefore carries the tooling, the guardrail harness, the offline model client,
and the ATS forms Phase 1 fills. The mail corpus, the two evidence profiles, and the outcome
backfill each sit at the head of the single phase that reads them — a corpus held in Phase 0 that
nothing is yet waiting for turns a precondition into a delay.

| Phase | Milestone | Epic | Spike | Risks retired |
|---|---|---|---|---|
| 0 | Foundations, fixtures, and the guardrail harness | [#1](https://github.com/sid-ak/TalentAgent/issues/1) | — | R6 |
| 1 | Two-pass apply, deterministic execution | [#11](https://github.com/sid-ak/TalentAgent/issues/11) | A | R1 |
| 2 | Evidence graph and credited composition | [#19](https://github.com/sid-ak/TalentAgent/issues/19) | B | R2 |
| 2.5 | Interactive demo and review surface | — | — | — |
| 3 | The autonomous inbound pipeline | [#29](https://github.com/sid-ak/TalentAgent/issues/29) | D | R4 |
| 4 | Opportunity scoring and the analyst loop | [#39](https://github.com/sid-ak/TalentAgent/issues/39) | C, E | R3, R5 |
| 5 | Production deployment and acceptance | [#49](https://github.com/sid-ak/TalentAgent/issues/49) | — | — |

Each phase's epic holds the task checklist, and every task issue cites the specification sections and
decision records it implements.

Phases 3 and 4 can proceed in either order once Phase 0 is complete; they are numbered this way
because the pipeline feeds the outcome log the analyst reads, and having real rows alongside the
backfill makes the analyst's first findings more informative.

---

## 2. Phase 0: Foundations, fixtures, and the guardrail harness

Goal: everything that must exist before an agent may be written. That is a repository that lints and
tests, a state layer whose rules are enforced rather than intended, a model client that can be run
offline, and the six fixture sets in Spec §13.2.

Scope

- Python package layout, tooling, lint gates, and docstring enforcement.
- CI on GitHub Actions: lint, type check, test, and an assertion that the suite reached no network.
- A model client with tier-1 and tier-2 routing, and a record-and-replay layer that turns recorded
  responses into golden fixtures.
- The tool registry with side-effect classes (Spec Appendix C), and the guardrail suite asserting
  G1 through G7.
- A fetch wrapper enforcing the permitted-domain allowlist (G5) and treating third-party text as
  data (G7).
- ATS form fixtures for all three platforms: the corpus Phase 1 fills against.

Exit criteria

- `mkdocs build --strict` and the full test suite are green in CI.
- The test suite makes zero model API calls, asserted rather than assumed.
- `submit_application` is unreachable from every agent path, asserted in a test.

Blocks every other phase.

Four items first written here are owned by later phases, each by the one phase that reads it: the
Firestore collections and rules and the two evidence profiles by Phase 2, the mail corpus by
Phase 3, and the outcome backfill by Phase 4. The exit criterion that `outcomes` is provably
append-only travels with the rules to Phase 2, and Spec §13.2's requirement that every fixture
exists and is anonymised is now met corpus by corpus rather than all at once.

---

## 3. Phase 1: Two-pass apply, deterministic execution

Goal: retire R1. A form on a live third-party ATS fills itself correctly, from a package, without a
model driving the browser and without any path that could submit it.

Only Pass 2 is built here. Composition is Phase 2, and the two are separated for the reason in
[ADR-0008](./ADRs/0008-deterministic-field-map.md): deciding what to say is a reasoning problem over
evidence, deciding where to put it is a mechanical problem over a DOM, and a single agentic loop
fails at both at once.

Scope

- A field-map schema and resolver: field selector to package path, per platform.
- Field maps and fixture fills for Greenhouse, Lever, and Ashby.
- A bounded model fallback for unmapped custom fields only, logged per invocation.
- Halt-and-capture: a screenshot of the completed form, a per-field miss record, and a run artifact.
- The `form-worker` workflow on GitHub Actions, triggered by `workflow_dispatch`.

Exit criteria (Spike A)

- At least 90% field completion on fixtures, per platform. A platform that cannot reach 90% is
  dropped rather than the criterion lowered.
- One clean end-to-end run against a live posting, per platform.
- Zero submissions from any non-human path, asserted in tests.

The first and third are settled in this phase, on fixtures and in CI. The live runs need a person at
a real employer's page, so they are executed in Phase 5 through the same dispatch bridge a user
would use, and the gate document reports the criterion as outstanding until they exist rather than
reporting a pass. What Phase 1 establishes is that the approach works and which platforms survive;
what the live runs add is that the maps hold against a real DOM.

---

## 4. Phase 2: Evidence graph and credited composition

Goal: retire R2. Every generated line traces to something the user actually said or did, and where
nothing supports a requirement the system reports a gap instead of writing around it.

Scope

- The Firestore collections, the security rules implementing the write-ownership table, and the
  emulator harness. `outcomes` is append-only by rule; the single-writer invariant is expressed as
  rules keyed to a component claim (Architecture §5.1). This is the first phase writing durable
  documents a later phase reads back, and the typed models it defines are shared by every writer
  after it.
- The two evidence profiles: one real repository ingested into artifacts, and a second profile built
  entirely from elicited statements with no public artifacts at all.
- The evidence graph: node and edge types, and the invariants in Spec §3.4.
- Attestation classes, and the quarantine that keeps `derived` nodes out of composition
  ([ADR-0002](./ADRs/0002-graded-attestation-classes.md)).
- The evidence sync job: artifact ingest, clustering into candidate accomplishments, metric
  attachment.
- Retrieval with sufficiency scoring, per requirement.
- Constrained composition — Pass 1 — emitting credited bullets and credited screening answers.
- Package schema validation that rejects an uncredited line at the schema layer, not in prompt text.
- The gap contract, `FLAG` versus `ELICIT`, and elicitation: one scoped question at a time, with the
  user's own words becoming the Statement node.
- Coverage reported per attestation class, and credit trace-through to a viewable source.

Exit criteria (Spike B)

- `outcomes` is proven append-only: update and delete are denied by rule, asserted against the
  emulator.
- 100% credit coverage, reported split by class.
- Zero `derived` leakage into any package.
- An adversarial posting yields gaps and questions rather than inventions.
- The profile with no public artifacts produces a fully credited application.

---

## 5. Phase 2.5: Interactive demo and review surface

Goal: the interactive human review surface and demonstrable UI. A review gate where every line is
clickable through to what justifies it, gaps are interactive deliverables with live elicitation,
candidates can manage custom profiles, and ATS form filling is visualised with human-only gates.

Scope

- Candidate profile management: upload resume (PDF parsing via `pypdf`), ingest GitHub repositories,
  add LinkedIn references, and write verbatim accomplishment statements alongside preset Profile A
  (engineering artifacts) and Profile B (non-engineering statements).
- The review UI: package review with credit trace-through, gaps shown as a deliverable rather than an
  error list, and coverage displayed per class.
- Interactive evidence graph explorer: visual node graph (Artifacts, Statements, Skills, Metrics,
  Accomplishments) with attestation class filtering and visual representation of the derived
  quarantine boundary.
- Live elicitation and statement promotion: interactive scoped question answering promoting raw text
  verbatim into the graph and triggering real-time re-composition.
- ATS execution playback: step-by-step form fill visualization across Greenhouse, Lever, and Ashby
  with field resolution mapping, completion meters, and human-only submission gate enforcement.
- System guardrail and zero-budget resource monitor: live display of Invariants G1 through G7 and daily
  Gemini Flash quota tracking.
- Static Angular application in `frontend/` built into `web/`, with a zero-dependency Python API
  server in `talentagent/ui/`.

Exit criteria

- Interactive Angular review UI successfully builds and serves locally and statically.
- Candidate profiles (Profile A, Profile B, custom) compose packages with 100% credit coverage.
- Adversarial posting yields 100% gaps and zero hallucinations live in the UI.
- Scoped elicitation answers promote verbatim into the graph and update composition in real time.
- `submit_application` remains human-only and disabled for automated agents across all views.

---

## 6. Phase 3: The autonomous inbound pipeline

Goal: retire R4. Application state maintains itself from the inbox and the calendar, with no user
action, and silence is detected as its own signal.

Scope

- The labelled mail corpus and its anonymisation pipeline: roughly 150 real messages, each carrying
  all three labels, with a held-out split so the corpus can measure rather than only fit.
- The Apps Script project, `clasp` deployment, and time-driven triggers on the adaptive cadence:
  hourly on weekday working hours, every six hours otherwise.
- The `lastHistoryId` cursor and per-message idempotency keys.
- Batched tier-1 triage — one call over the run's messages rather than one per message.
- Thread attribution, deterministic first and model-assisted only on failure.
- The state machine, the transition contract, and the confidence gate that proposes rather than
  applies below threshold.
- Time-derived `GHOSTED`, the only transition with no triggering message.
- State-conditional side effects: a tentative calendar hold on `SCREEN`, a follow-up draft on
  `GHOSTED`, escalation on `OFFER`.

Exit criteria (Spike D)

- At least 95% classification precision and 90% transition accuracy against the labelled corpus.
- Overlapping triggers provably do not double-advance state.
- A message received is reflected in state by the end of the next scheduled run.

---

## 7. Phase 4: Opportunity scoring and the analyst loop

Goal: retire R3 and R5. Two scores exist, they are never merged, and only one of them is allowed to
exclude an opportunity. The analyst closes one full loop: hypothesis, experiment, measured result,
next hypothesis.

Scope

- The outcome backfill: historical applications with known results, spanning every segment the
  analyst reads and including one segment with zero replies, so `INSUFFICIENT_EVIDENCE` has
  something real to render and the loop can be measured before the pipeline has produced months of
  live rows.
- The eligibility corpus, ingested from one public structured filing dataset, aggregated and
  recency-weighted, with conflicting signals surfaced individually rather than averaged.
- `score_eligibility` — the only score permitted to gate.
- Prior computation with posterior intervals, decay by half-life, and the `INSUFFICIENT_EVIDENCE`
  state that is distinct from `WEAK`.
- Ranking rules enforcing G4: `may_exclude` is `false` on every prior record.
- Segment analysis over the outcome log, in-process, with declared confounds.
- Hypothesis formation and experiment registration, one variable and one segment at a time.
- The exploration budget: a declared, reported ε targeting segments by interval width rather than by
  low mean ([ADR-0004](./ADRs/0004-exploration-budget.md)).
- Finding expiry and re-queue ([ADR-0009](./ADRs/0009-findings-expire.md)), and the assignment rules
  the composer reads — the system's only cross-agent influence, and it travels through state.
- The nightly `analyst` workflow on GitHub Actions.

Exit criteria (Spikes C and E)

- One hypothesis resolved end to end, with a second actively assigning.
- A zero-reply segment still appears in ranked output, labelled `INSUFFICIENT_EVIDENCE`.
- Every eligibility score traces to a named public source.
- Eligibility is the only score able to exclude, asserted in tests.
- The exploration budget is honoured and visible in the outcome log.

---

## 8. Phase 5: Production deployment and acceptance

Goal: production deployment and acceptance verification. A deployment that works from a clean
project, and a run against the Definition of Done.

Scope

- Firebase Auth, Firebase Hosting deployment, and the `workflow_dispatch` bridge to the form worker.
- The outstanding Spike A criterion: one clean end-to-end run against a live posting per platform,
  dispatched through that bridge, with the artifact retained as the evidence.
- Measurement: the metrics in Spec §12 collected and reported, including tier-down rate and daily
  quota consumption.
- Deployment verified from a clean project, with a runbook covering trigger installation and
  API-key entry.

Exit criteria

- Every box in Spec §14 ticked, with the evidence for each recorded.
- Deploy verified from a clean project.

---

## 9. Risk coverage

Every risk in Spec §13.1 is retired by a named phase gate rather than by general progress.

| Risk | Retired by | Gate |
|---|---|---|
| R1 — server-side fill unreliable on live forms | Phase 1 | 90% fixture completion per platform; one clean live run each |
| R2 — generation fabricates where evidence is absent | Phase 2 | Zero `derived` leakage; adversarial posting yields gaps |
| R3 — analyst hardens what little data it has | Phase 4 | Intervals reported; exploration budget honoured; findings expire |
| R4 — classification and attribution are noisy | Phase 3 | 95% precision, 90% transition accuracy |
| R5 — eligibility scoring is confidently incorrect | Phase 4 | Every score traces to a named public source |
| R6 — free-tier quota throttles development | Phase 0 | Golden fixtures; test suite makes zero API calls |

## 10. Definition of Done coverage

Spec §14 is the acceptance list. Each item is owned by the phase that produces it, and Phase 5
verifies the whole list rather than re-deriving it.

| Definition of Done item | Owning phase |
|---|---|
| Three platforms fill at ≥90% on fixtures | 1 |
| One clean live run per platform | 5 |
| 100% credit coverage, split by attestation class | 2 |
| Zero `derived` claims reach a package | 2 |
| Adversarial posting produces gaps, not fabrications | 2 |
| The no-public-artifacts profile produces a fully credited application | 2 |
| Interactive review surface with credit trace and live elicitation | 2.5 |
| One experiment resolved end to end; a second actively assigning | 4 |
| Priors report intervals; a zero-reply segment stays visible | 4 |
| Only eligibility can exclude | 4 |
| Exploration budget honoured and visible in the outcome log | 4 |
| Inbound path on the adaptive schedule, batched triage, idempotency tests | 3 |
| Tier-down rate measured; quota consumption inside free-tier ceilings | 3, 5 |
| Test suite makes zero model API calls | 0 |
| `outcomes` proven append-only | 2 |
| `submit_application` unreachable from any agent path | 0, 1 |
| Deploy verified from a clean project | 5 |
| Architecture documented, including the asynchronous path | 5 |
