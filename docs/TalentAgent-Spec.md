# TalentAgent Specification

An event-driven multi-agent system that operates a job search as a long-running workflow. Five specialist agents maintain an evidence graph of the user's accomplishments, derive application pipeline state from the user's inbox, compose applications in which every generated claim is traceable to user-originated evidence, and run a closed experiment loop over application outcomes. The system takes autonomous action on preparation, tracking, and analysis; irreversible and identity-asserting actions remain human-only.

---

## Table of Contents

1. [Overview and Goals](#1-overview-and-goals)
2. [System Model](#2-system-model)
3. [Evidence Graph](#3-evidence-graph)
4. [Application Pipeline](#4-application-pipeline)
5. [Application Package](#5-application-package)
6. [Opportunity Scoring](#6-opportunity-scoring)
7. [Analyst](#7-analyst)
8. [Coordination](#8-coordination)
9. [Tool Surface](#9-tool-surface)
10. [Guardrails](#10-guardrails)
11. [Persistence](#11-persistence)
12. [Measurement](#12-measurement)
13. [MVP Scope](#13-mvp-scope)
14. [Definition of Done](#14-definition-of-done)
15. [Future Scope](#15-future-scope)

Appendices: [A. Attestation Classes](#appendix-a-attestation-classes) · [B. State Transitions](#appendix-b-state-transitions) · [C. Side-Effect Classes](#appendix-c-side-effect-classes) · [D. Non-Goals](#appendix-d-non-goals)

---

## 1. Overview and Goals

### 1.1 Problem Statement

Tools in the job-search category optimize the production of an application. Production is not the bottleneck. The unaddressed cost is distributed across a multi-week workflow: determining whether an application is worth sending, re-entering the same history into successive forms, tracking which of forty applications remain live, detecting silence, and extracting any signal from outcomes.

Three properties make this workflow poorly suited to manual operation and to chat interfaces:

- **It is long-running and stateful.** The relevant unit is an application that lives for six to twelve weeks, not a single request.
- **Its feedback signal is sparse and delayed.** Outcomes arrive weeks after the decision that caused them, in volumes too small for informal inference.
- **Its authoritative state lives elsewhere.** The truth about an application's status is in the user's inbox and calendar, not in any tracker the user maintains by hand.

TalentAgent treats the search as a pipeline to be derived, a dataset to be analyzed, and an evidence base to be argued from.

### 1.2 Design Principles

**Derived state, not entered state.** Application status is computed from observed inbox and calendar events. Any system requiring sustained manual upkeep is abandoned in use, and a stale tracker asserts false information with authority.

**Evidence-constrained generation.** The composition step receives retrieved evidence as its only admissible input. It selects and phrases; it does not introduce. The guarantee is narrow and complete: the system never originates a claim the user did not make.

**Graded provenance.** Provenance is not binary. Most accomplishments are not public and many are not artifacts. Each claim carries an attestation class recording how strongly it is backed, and model-originated claims are barred from reaching an employer.

**Autonomy bounded by authority, not by capability.** The system performs all preparation, tracking, and analysis without prompting. It does not perform actions that assert identity — authenticating, proving personhood, or submitting claims under the user's name.

**Separation of gating from ranking.** Externally verifiable facts may exclude an opportunity. Estimates derived from the user's own sparse outcome history may only reorder one.

**Falsifiable analysis.** Findings carry sample size, uncertainty, and expiry. A fixed share of assignments is spent testing segments the system currently rates poorly, so conclusions remain contestable by the system itself.

**Coordination through state, not calls.** Agents do not invoke one another. All coordination is by typed events over durable state, which makes each step replayable, auditable, and independently testable.

### 1.3 Scope and Layering

This specification defines the agent contracts, data schemas, coordination semantics, tool surface, and guardrails. It does not define deployment topology, service boundaries, or networking; those are given in the architecture document.

The system targets three applicant tracking platforms (Greenhouse, Lever, Ashby). Platforms whose terms prohibit automated interaction are out of scope by design, not by limitation: the inbox, the calendar, user-supplied postings, and public job-board endpoints cover the full workflow without them.

### 1.4 Human-Retained Actions

The following remain human-only and are not exposed to any agent:

| Action | Rationale |
|---|---|
| Account creation | Identity assertion; also a credential operation |
| Authentication | Credential operation; not required on the target platforms (Section 8.3) |
| Bot-detection challenges | Assertion of personhood; occurs at submit, where a human is already present |
| Application submission | Irreversible; asserts the claims as the user's own |
| Offer acceptance or decline | Irreversible and consequential |

These actions occupy seconds per application and recur rarely. The preparation, tracking, and analysis they bracket occupy the remainder of the workflow and are fully automated.

---

## 2. System Model

### 2.1 Agent Roster

Agents are defined by the fields they exclusively write.

| Agent | Trigger | Reads | Exclusively writes | Prohibited from |
|---|---|---|---|---|
| `triage` | Inbound mail event | Raw message | `message_classification` | Interpreting beyond a label |
| `pipeline` | `message.classified` | Classification, application state | `application.state`, `timeline[]`, `draft_action` | Sending anything |
| `evidence` | Sync schedule, user answer | Artifacts, statements, calendar | `evidence_graph` nodes and edges | Reading job postings; authoring a Statement |
| `composer` | `apply.requested` | Posting spec, evidence graph | `application_package`, `credits[]`, `gaps[]` | Submitting a form |
| `analyst` | Analysis schedule | Outcome log, eligibility corpus | `hypothesis`, `experiment`, `finding` | Mutating application state |

### 2.2 Responsibility Contracts

**Single-writer invariant.** Exactly one agent owns each field. Cross-agent influence is expressed as an event or as state another agent reads, never as a write or a call. Any unexpected value therefore has exactly one responsible agent.

**Escalation as a terminal outcome.** Any agent may terminate with `ESCALATE(reason, payload)` in place of a result. Escalation is a defined outcome, not an error path, and its rate per decision point is a reported metric (Section 12).

### 2.3 Trigger Classes

| Class | Source | Delivery | Example |
|---|---|---|---|
| `event` | Gmail poll on an adaptive schedule | At-least-once, cursor-driven | Recruiter reply arrives |
| `schedule` | Cron | Exactly-once per window | Nightly analysis, evidence sync |
| `intent` | User action | Synchronous | Posting URL supplied; review decision |

At-least-once delivery requires all event-driven writes to be idempotent (Section 8.6). The `event` class is scheduled polling rather than a push subscription: hourly during weekday working hours, every six hours overnight and at weekends. Recruiter correspondence moves on a scale of half a day to several days, so nothing in the workflow is sensitive to sub-hour latency. See ADR-0005 and ADR-0012, and Architecture §10 for the upgrade path.

---

## 3. Evidence Graph

### 3.1 Node and Edge Types

```
Node types:  Artifact       (commit | PR | doc | design | ticket | course | calendar_event)
             Statement      (the user's dated assertion, in the user's own words)
             Accomplishment (a claim; requires >= 1 supporting Artifact or Statement)
             Skill          (canonical technology or capability)
             Metric         (typed measured outcome: value, unit, basis)

Edge types:  EVIDENCES      Artifact | Statement -> Accomplishment
             DEMONSTRATES   Accomplishment       -> Skill
             QUANTIFIES     Metric               -> Accomplishment
             SUPERSEDES     Accomplishment       -> Accomplishment
```

`SUPERSEDES` allows a better-evidenced claim to retire an earlier one without deleting history.

### 3.2 Attestation Classes

A graph restricted to public artifacts describes only applicants whose work is public and whose access to it persists. Most accomplishments are held in private repositories, inaccessible internal systems, or are decisions and leadership that produced no artifact.

Admitting user-asserted evidence introduces a circularity risk: if user assertion counts as evidence, a credit certifies nothing. The resolution is to state the guarantee precisely. The guarantee is not that a third party verified the claim; it is that the model did not originate it. That boundary is unaffected by the presence or absence of an artifact.

| Class | Definition | Admissible in a package |
|---|---|---|
| `verifiable` | Resolves to a source a third party can inspect | Yes |
| `corroborated` | Private artifact the user holds and can produce on request | Yes |
| `attested` | The user's dated statement; no artifact | Yes, labeled |
| `derived` | Proposed by the model from other evidence | No — quarantined until user confirmation promotes it to `attested` |

Truthfulness of an `attested` claim is the user's responsibility. It is made in the user's words, under the user's name, on the user's application. The system does not adjudicate it and does not claim to.

### 3.3 Accomplishment Schema

Artifact-backed:

```json
{
  "id": "acc_7f21",
  "claim": "Cut p99 ingest latency by tiering the classifier",
  "skills": ["skill_pubsub", "skill_python", "skill_model_routing"],
  "metrics": [{"name": "p99_latency", "delta": -0.62, "unit": "ratio", "basis": "prod dashboard, 30d"}],
  "evidence": ["art_pr_412", "art_pr_419", "art_doc_designreview"],
  "class": "verifiable",
  "period": {"start": "2025-03", "end": "2025-06"},
  "confidence": 0.91,
  "derived_by": "evidence@2026-08-14T03:12Z"
}
```

Statement-backed, which is the expected majority case:

```json
{
  "id": "acc_2b88",
  "claim": "Led the migration of 40 services to a new auth provider",
  "skills": ["skill_auth", "skill_migration", "skill_leadership"],
  "metrics": [{"name": "services_migrated", "value": 40, "unit": "count", "basis": "user-stated"}],
  "evidence": ["stm_0091"],
  "class": "attested",
  "statement": {
    "raw": "i ran the auth migration last year, about 40 services, took two quarters, i was driving it not just contributing",
    "elicited_by": "gap:req_5 on job_9a2",
    "asserted_at": "2026-08-14",
    "artifact_producible": false
  }
}
```

| Field | Type | Required | Description |
|---|---|---|---|
| `claim` | String | Yes | Canonical statement of the accomplishment |
| `evidence` | List | Yes | Artifact or Statement IDs; must be non-empty |
| `class` | Enum | Yes | Attestation class (Section 3.2) |
| `metrics` | List | No | Typed outcomes; `basis` records how each was obtained |
| `statement.raw` | String | If `attested` | The user's verbatim text, stored unmodified |
| `period` | Object | No | Time range the claim covers |
| `confidence` | Float | No | Clustering confidence for derived accomplishments |

### 3.4 Invariants

1. **Non-empty provenance.** Every Accomplishment references at least one Artifact or Statement.
2. **No model-originated claims.** An Accomplishment of class `derived` cannot be selected by the composer. It is surfaced for confirmation and enters the usable graph only on user promotion.
3. **Verbatim retention.** `statement.raw` is stored exactly as written, separately from any generated text derived from it. Credits display the raw text, so generated phrasing cannot drift from the user's assertion without the drift being visible.

### 3.5 Elicitation

Most of the graph cannot be harvested and must be supplied by the user. A form is not an acceptable intake mechanism: it depends on sustained discipline, which fails for the same reason manual trackers fail. Intake is therefore demand-driven and scoped. Two triggers are defined; no others.

**Trigger 1 — gap-driven.** A gap with no usable evidence emits one question, scoped to the missing requirement, attached to the application under review. The marginal cost to the user is one sentence, incurred while examining a posting they have chosen to pursue, and the resulting node is reusable by every subsequent package.

```
composer -> gap(req_5, sufficiency 0.0)
    -> elicit_evidence(gap)          one question, scoped to the requirement
        -> user answers in own words
            -> Statement node        raw text retained verbatim
                -> Accomplishment    class = attested
```

**Trigger 2 — retrospective.** On project close or detected milestone, the evidence agent elicits while the details remain accurate rather than at search time, when metrics and context have decayed. This is the system's primary activity between active searches.

Rules:

- One question at a time, scoped to a specific gap. Questionnaires are not permitted.
- The model does not author the Statement. It asks; the user's words become the node. Model-composed answers are `derived` and quarantined.
- Questions request specifics: quantity, timeframe, and the user's role relative to the team's.

---

## 4. Application Pipeline

### 4.1 State Machine

```
                 ┌─────────► REJECTED ◄────────┐
                 │                              │
DISCOVERED ─► PREPARED ─► SUBMITTED ─► ACKED ─► SCREEN ─► ONSITE ─► OFFER
                 │                       │         │         │
                 └──► ABANDONED          └─────────┴─────────┴──► GHOSTED
```

### 4.2 Transition Contract

Every transition record carries:

| Field | Type | Description |
|---|---|---|
| `from`, `to` | Enum | Source and target states |
| `evidence_message_id` | String | Triggering message; null only for time-derived transitions |
| `confidence` | Float | Classifier confidence |
| `decided_by` | String | Agent and version |
| `at` | Timestamp | Decision time |

### 4.3 Derivation Rules

- **State is derived, never entered.** Transitions are computed from observed events.
- **`GHOSTED` is time-derived.** It is entered when a per-state silence threshold elapses (default: 12 days after `SCREEN`). It is the only transition with no triggering message, and it is the mechanism by which staleness is detected without user action.
- **Monotonic except by explicit correction.** A low-confidence classification cannot walk state backwards.
- **Confidence gate.** Below threshold, a transition is proposed rather than applied and surfaces for review.

---

## 5. Application Package

### 5.1 Schema

```json
{
  "posting_id": "job_9a2",
  "bullets": [
    {
      "text": "Reduced p99 ingest latency 62% by tiering model routing",
      "credits": ["acc_7f21"],
      "class": "verifiable",
      "artifacts": ["art_pr_412", "art_pr_419"],
      "requirement_ids": ["req_3", "req_7"]
    },
    {
      "text": "Led a 40-service migration to a new auth provider over two quarters",
      "credits": ["acc_2b88"],
      "class": "attested",
      "artifacts": [],
      "requirement_ids": ["req_2"]
    }
  ],
  "screening_answers": [
    {"question_id": "q_yoe_python", "value": "4", "credits": ["acc_7f21", "acc_1c04"]}
  ],
  "gaps": [
    {"requirement_id": "req_5", "text": "5+ years Kubernetes in production",
     "best_available": null, "sufficiency": 0.0, "action": "ELICIT",
     "question": "Nothing in the graph touches Kubernetes. Has it been run in production, where, and for how long?"}
  ],
  "coverage": {"total": 0.78, "verifiable": 0.31, "corroborated": 0.22, "attested": 0.25}
}
```

### 5.2 Credit Contract

- Every generated line carries at least one credit and its attestation class.
- A line without a valid credit, or backed by a `derived` node, fails schema validation and does not reach the user.
- Enforcement is at the schema layer, not in prompt text.
- Credits resolve to a viewable source: an artifact, a private artifact reference, or the user's verbatim statement.

### 5.3 Gap Contract

`gaps[]` is a deliverable, not an error list. A requirement below the sufficiency threshold produces a gap rather than generated text. Where no usable evidence exists, the gap carries an elicitation question (Section 3.5).

| `action` | Condition | Behavior |
|---|---|---|
| `FLAG` | Partial evidence exists below threshold | Report requirement, best available evidence, sufficiency |
| `ELICIT` | No usable evidence | Report requirement and emit one scoped question |

### 5.4 Coverage Reporting

Coverage is reported per attestation class and never as a single scalar. A package fully covered by `attested` credits and one fully covered by `verifiable` credits are materially different objects.

### 5.5 Two-Pass Apply

**Pass 1 — Compose.** Fetch posting; extract normalized `requirement[]` and screening questions; retrieve evidence per requirement; emit credited bullets, credited answers, and `gaps[]`. Executes offline and is testable against fixtures.

**Pass 2 — Execute.** Drive the ATS form server-side. Enumerate fields; resolve each against a per-platform deterministic field map; fall back to the model only for unmapped fields. Upload materials. Capture a screenshot of the completed form. Halt.

Separating composition from execution keeps the non-deterministic component offline and testable, and confines model involvement in the live form to unmapped custom fields. A single model-driven browser loop couples both failure modes and is not used.

**Termination.** Pass 2 ends in a completed, unsubmitted form. `submit_application` is a human-only capability with no agent-reachable path (Section 9.1).

---

## 6. Opportunity Scoring

### 6.1 Score Types

Two scores are computed. They are distinct objects with distinct powers and are never merged into one value.

| Property | `eligibility` | `prior` |
|---|---|---|
| Nature | Fact about the world | Estimate about the user |
| Source | Public structured filings; posting declarations | The user's own outcome log |
| Sample | External, large, independent of the user | Small, biased, aging |
| Failure mode | Stale data | Confounding, small-n, self-confirmation |
| Power | May gate (exclude) | May rank only |

### 6.2 Eligibility Record

```json
{
  "employer_id": "emp_331",
  "sponsorship": {
    "score": 0.82,
    "signals": [
      {"source": "public_filing_disclosure", "period": "2024-2026",
       "count": 47, "roles_matching_archetype": 12},
      {"source": "posting_declaration", "value": "will_sponsor"}
    ],
    "recency_weighted": true,
    "caveat": "Rule changes in the current period may reduce forward-looking validity",
    "confidence": "medium",
    "gating": true
  }
}
```

Signals derive from public structured filings and the posting's own declared answers only. Model recollection of an employer is not a signal. Conflicting signals are surfaced individually and are not averaged.

### 6.3 Prior Record

```json
{
  "segment": {"channel": "aggregator_portal", "role_archetype": "backend"},
  "observed": {"n": 8, "replies": 0, "window_days": 90},
  "estimate": {
    "posterior_mean": 0.06,
    "interval_90": [0.00, 0.19],
    "prior": "beta(1,8) — pooled across segments",
    "effective_n": 6.2,
    "decay_half_life_days": 60
  },
  "state": "INSUFFICIENT_EVIDENCE",
  "confounds": ["company_stage", "sponsorship_available", "resume_variant"],
  "rank_effect": -0.12,
  "may_exclude": false
}
```

Four properties prevent the record from expressing unearned confidence:

- **Intervals, not point estimates.** Zero replies from eight sends yields an interval wide enough to preclude a conclusion, and the schema reports it as such.
- **A third state.** `INSUFFICIENT_EVIDENCE` is distinct from `WEAK`. Absence of sampling and negative sampling are different claims and render differently.
- **Declared confounds.** Channel is not randomly assigned; portal applications correlate with employer size, fit, and sponsorship availability. Named confounds prevent a segment effect being read as causal.
- **Decay.** Outcomes are recency-weighted by half-life. Older outcomes describe a candidate whose evidence graph and materials have since changed.

`may_exclude` is `false` on every prior record. The field exists to make the invariant explicit and assertable in tests; it is not configurable.

### 6.4 Ranking Rules

1. Only `eligibility` may remove an opportunity from output.
2. `prior` adjusts order and must display its state and interval.
3. No opportunity is suppressed without an externally sourced reason.

---

## 7. Analyst

### 7.1 Hypothesis, Experiment, Finding

```json
{
  "hypothesis_id": "hyp_014",
  "statement": "Direct-to-company applications outperform aggregator portals for backend roles",
  "segment": {"role_archetype": "backend", "company_stage": ["seed","series_a","series_b"]},
  "variable": "application_channel",
  "baseline": {"n": 41, "callback_rate": 0.073},
  "experiment": {"assignment": "next 10 in segment -> direct", "min_n": 10, "horizon_days": 14},
  "status": "RESOLVED",
  "finding": {"n": 12, "callback_rate": 0.25, "effect": 3.4,
              "confidence": "low-n, directional", "adopted": true,
              "expires_after_days": 90, "confounds_unresolved": ["company_stage"]}
}
```

| Constraint | Requirement |
|---|---|
| Falsifiability | A hypothesis names one variable and one segment |
| Honesty | Every finding carries `n` and an explicit strength qualifier |
| Expiry | Every finding carries `expires_after_days`; on expiry it ceases to influence ranking and returns to the hypothesis queue |
| Confounds | Unresolved confounds are recorded on the finding |

Findings are maintained, not accumulated. A finding without expiry converts a measurement into a permanent assumption.

### 7.2 Exploration Budget

A purely greedy assignment policy is self-confirming: a down-ranked segment receives no further traffic, collects no data, and retains its initial estimate indefinitely.

```
For each application to be assigned:
    with probability ε  -> assign to a segment in {INSUFFICIENT_EVIDENCE ∪ lowest-prior}
    otherwise           -> assign to the current best segment
```

- `ε` is a declared, reported budget, not an internal constant.
- Exploration targets segments by **interval width**, not by low mean. Information is located in uncertainty; a confidently poor segment yields less than an unsampled one.
- Exploration assignments are labeled in the outcome log and excluded from exploit-side effect estimates.
- Findings retired by expiry become eligible for exploration, which is the mechanism by which stale conclusions are retested.

### 7.3 Loop Closure

The analyst does not act on applications. It registers an assignment rule that the composer reads. This is the only cross-agent influence in the system, and it propagates through state rather than through a call.

---

## 8. Coordination

### 8.1 Inbound Mail Flow

```
Gmail change trigger -> advance cursor -> triage (tier 1)
    ├─ not job-related (majority) -> drop, log, terminate
    └─ job-related -> message.classified
                        -> pipeline (tier 2)
                             ├─ resolve thread -> application_id
                             ├─ propose transition + confidence
                             ├─ confidence >= τ -> apply; else -> propose for review
                             ├─ state-conditional side effects:
                             │     SCREEN  -> hold_calendar_slot
                             │     OFFER   -> escalate
                             │     GHOSTED -> draft_followup
                             └─ append immutable row -> outcome log
```

Thread attribution is resolved deterministically where possible — thread ID, ATS reference, employer domain — and handed to the model only on failure. Attribution is predominantly a retrieval problem and is not priced as a reasoning problem.

**Batched triage.** Because the cadence is hourly rather than continuous, each run typically finds several messages. Tier-1 classification is issued as one call over the batch rather than one call per message, which is the principal reason the cadence was widened (ADR-0005).

### 8.2 Evidence Sync

Scheduled. Ingest new artifacts; cluster into candidate accomplishments; attach metrics where an artifact states one; classify each as `verifiable` or `corroborated`. Anything the model assembled rather than read is written as `derived` and held for confirmation. The same job carries elicitation trigger 2 (Section 3.5).

### 8.3 Apply Flow

Triggered by user intent. Eligibility check, composition (Pass 1), execution (Pass 2), halt for human review and submission.

**No authenticated session.** The three target platforms accept applications without a candidate account, so composition and fill run unauthenticated and no ATS credential or session exists anywhere in the system. A platform requiring authentication would need a delegation mechanism, which is out of scope for this build and specified as future work in Section 15.1.

### 8.4 Nightly Analysis

Scheduled. Expire findings past horizon and return them to the queue; resolve experiments past horizon and write findings; recompute priors with decay; segment the outcome log across variant, channel, company stage, role archetype, and time-to-post; form the next hypothesis on the segment with the largest defensible effect; register the resulting assignment rule.

### 8.5 Escalation

Any agent may terminate with `ESCALATE`. Handling is uniform: apply a registered deterministic fallback rule for that decision if one exists; otherwise halt the workflow instance and surface it. Escalation rate per decision point is reported.

### 8.6 Idempotency and Ordering

- **Cursor.** The mail path advances a `lastHistoryId` cursor, so overlapping triggers do not reprocess the same window.
- **Idempotency key.** Every event-driven transition is additionally keyed on `evidence_message_id`. Reprocessing does not double-advance state.
- **At-least-once delivery.** All event handlers are idempotent; no handler assumes exactly-once semantics.
- **Immutable history.** Corrections append; they do not rewrite. An analytic finding cannot be silently altered by a later state correction.

---

## 9. Tool Surface

### 9.1 Tool Registry

| Tool | Side-effect class | Notes |
|---|---|---|
| `classify_message` | `pure` | Tier-1 backed |
| `fetch_posting(url)` | `read` | Permitted-domain list enforced at fetch layer |
| `query_evidence(requirement)` | `read` | Returns candidates, sufficiency, class |
| `score_eligibility(employer, archetype)` | `read` | Structured filings only; may gate |
| `score_prior(segment)` | `read` | Returns interval and state; rank-only |
| `run_segment_analysis(spec)` | `read` | In-process over the outcome log |
| `elicit_evidence(gap)` | `write-draft` | Emits one scoped question; cannot author a Statement |
| `promote_statement(answer)` | `write-user-originated` | User's raw text becomes a Statement and an `attested` accomplishment |
| `draft_followup(app_id)` | `write-draft` | Produces a draft; cannot send |
| `hold_calendar_slot(...)` | `write-reversible` | Tentative holds only |
| `fill_application(package)` | `write-staged` | Fills and captures; cannot submit |
| `submit_application(id)` | `human-only` | Not exposed to any agent; reachable only from a human review action |

### 9.2 Model Tiering

| Tier | Model | Role | Rationale |
|---|---|---|---|
| Tier 1 | Gemini Flash-Lite | Classification of every inbound message; posting-relevance filter | Most inbound mail is not job-related. Tier 1 decides whether tier 2 is needed. Flash-Lite carries a 4× larger free daily allowance than Flash. |
| Tier 2 | Gemini Flash | State reasoning, requirement-to-evidence mapping, constrained composition, hypothesis formation | Steps whose output is a judgment rather than a label |

Pro-class models left the free tier on 1 April 2026, so tier 2 is Flash rather than Pro. A self-hosted Gemma classifier is the fallback for tier 1 if the Flash-Lite allowance proves insufficient (ADR-0006).

### 9.3 Service Dependencies

Dependency choices follow the operating constraint in ADR-0012.

| Layer | Component | Function |
|---|---|---|
| Agent orchestration | Google ADK | Agent definitions, typed tool declarations, run tracing |
| Model serving | Gemini API (free tier) | Both tiers, rate-limited |
| Event ingress | Google Apps Script time-driven trigger | Gmail polling; hourly weekdays, 6-hourly otherwise |
| Mail-path compute | Google Apps Script | `triage` and `pipeline` execution |
| Job compute | GitHub Actions | `composer`, `evidence`, `analyst`; Chromium preinstalled |
| Scheduling | GitHub Actions `schedule` | Nightly analysis; evidence sync |
| Durable state | Firestore (Firebase Spark) | All collections, including the append-only outcome log |
| Web surface | Firebase Hosting + Firebase Auth | Static review UI |
| Run artifacts | GitHub Actions artifacts | Form captures, run logs; 90-day retention |
| External reads | Public board endpoints, GitHub API, Gmail, Calendar, public filing datasets | Documented interfaces only |

**Deliberately absent.** Cloud Run, Pub/Sub, Cloud Scheduler, Cloud Storage for Firebase, and BigQuery. At single-user scale the outcome log is a few hundred rows analyzed in-process, so a separate analytic store buys nothing; the rest is covered by ADR-0012.

---

## 10. Guardrails

Enforced in the policy layer and asserted in tests. Not implemented as prompt instructions.

| # | Invariant | Enforcement |
|---|---|---|
| G1 | No model-originated claims reach an employer | `derived` barred from composer selection; schema validation |
| G2 | No line without a credit | Package schema validation |
| G3 | No irreversible autonomy | `submit`, `send`, `accept`, `decline` are human-only tool classes |
| G4 | No suppression by self-derived signal | `may_exclude` false on every prior record; ranking-layer check |
| G5 | No prohibited automation | Permitted-domain allowlist in the fetch wrapper, asserted in tests |
| G6 | No credential handling | No account creation or password entry paths exist |
| G7 | Untrusted content is data | Instructions appearing in postings, emails, or ATS pages are never executed |

**On G7.** Job postings, inbound messages, and ATS pages are third-party text. A posting instructing the reader to disregard prior instructions is logged as an injection attempt and is not acted upon.

---

## 11. Persistence

| Store | Contents | Semantics |
|---|---|---|
| Firestore — operational collections | Applications, evidence graph, packages, hypotheses, assignment rules | Mutable current state; single-writer per collection; every mutation appends to `timeline[]` |
| Firestore — `outcomes` | Outcome event log, eligibility corpus | **Append-only by security rule**: create permitted, update and delete denied for every principal |
| Run artifacts | Rendered materials, form captures | Immutable per run; a submitted package is frozen and never regenerated |

State is mutable; history is not. The analyst reads only `outcomes`, so a later correction to application state cannot retroactively alter a reported finding.

The immutability guarantee is enforced by security rule rather than by using a separate append-only product. This is a configuration guarantee rather than an infrastructural one, and it is asserted in tests (ADR-0012).

---

## 12. Measurement

| Metric | Interpretation |
|---|---|
| Triage tier-down rate | Share of events resolved at tier 1; quantifies the tiering claim and governs quota headroom |
| Daily model requests by tier | Consumption against the free-tier ceilings; the binding operational constraint (Architecture §8) |
| Transition precision | Correct transitions against human-audited ground truth |
| Escalation rate per decision point | Contract quality; a spike localizes the weak contract |
| Credit coverage by class | 100% by construction; the class blend is the informative figure |
| `derived` leakage | Model-originated claims reaching a package. Must be zero. |
| Gap recall | Requirements correctly flagged versus written around |
| Elicitation conversion | Share of asked gaps producing a Statement |
| Graph growth per application | Reusable evidence gained per package; expected to fall as the graph saturates |
| Form completion rate per platform | Pass 2 reliability, per ATS |
| Experiments resolved | Loop closure, not merely loop initiation |
| Exploration budget spend | Whether `ε` was honored |
| Segments in `INSUFFICIENT_EVIDENCE` | Unexplored share of the space; expected to shrink |
| Findings expired versus retested | Whether stale conclusions are retired or inherited |

---

## 13. MVP Scope

### 13.1 Risk Register

Ordered by probability of invalidating the design multiplied by the cost of late discovery.

| # | Risk | Retired by |
|---|---|---|
| R1 | Server-side ATS fill is unreliable on live forms | Spike A |
| R2 | Generation fabricates where evidence is absent | Spike B |
| R3 | Analyst has insufficient data, then hardens what little it has | Spike C |
| R4 | Inbound classification and thread attribution are noisy | Spike D |
| R5 | Eligibility scoring is confidently incorrect | Spike E |
| R6 | Free-tier model quota throttles development below a workable pace | Golden-fixture responses in Phase 0; tier-1 routing; see Architecture §8 |

R1 and R2 are addressed first and in that order. If R1 cannot be retired, the system reshapes around Pass 1 and the analyst rather than continuing to invest in execution.

### 13.2 Phase 0 — Fixtures

No agent work begins until the following exist:

| Fixture | Contents | Purpose |
|---|---|---|
| ATS fixture set | Offline copies of real forms from all three platforms, including custom-question variants | Deterministic Pass 2 testing |
| Mail corpus | ~150 real messages labeled `{is_job_related, application_id, target_state}` | Ground truth for R4 |
| Evidence seed | One real repository ingested | Artifact-backed credit testing |
| Non-engineer profile | Second graph built entirely from elicited statements, no public artifacts | Proves the provenance design does not depend on a public repository |
| Outcome backfill | Historical applications with known results | Removes analyst cold start |
| Golden model responses | Recorded tier-1 and tier-2 outputs for every fixture | Test suite makes zero API calls: determinism, and the primary quota control (R6) |

### 13.3 Spike Criteria

| Spike | Builds | Passes when |
|---|---|---|
| **A** — Two-pass apply | Pass 2 against fixtures first, no model; deterministic field maps; model fallback for unmapped fields only; halt-and-capture; then live | ≥90% field completion on fixtures per platform; one clean end-to-end run against a live posting per platform; zero submissions from any non-human path |
| **B** — Credits | Attestation classes in the first schema; retrieval with sufficiency; constrained composition; schema-level rejection; gap and elicitation flow; trace-through | 100% credit coverage; zero `derived` leakage; adversarial posting yields gaps and questions, not inventions; non-engineer profile yields a fully credited application |
| **C** — Analyst | Prior computation with intervals before the hypothesis engine; segment analysis with declared confounds; hypothesis formation; experiment registration; exploration budget; resolution with expiry | One hypothesis resolved end to end; a second actively assigning; a zero-reply segment still appears in ranked output labeled `INSUFFICIENT_EVIDENCE` |
| **D** — Pipeline | Apps Script trigger with `lastHistoryId` cursor; batched tier-1 triage; deterministic attribution with model fallback; confidence gate; idempotency; time-derived `GHOSTED` | ≥95% classification precision; ≥90% transition accuracy; overlapping triggers provably do not double-advance; state reflects a message by the end of the next scheduled run |
| **E** — Eligibility | One public filing dataset, aggregated and recency-weighted; posting declarations; conflict surfacing | Every score traces to a named public source; eligibility is the only score able to exclude, asserted in tests |

If a platform cannot reach 90% on fixtures, that platform is dropped rather than the criterion lowered.

### 13.4 Scope Boundaries

| Ships | Stubbed | Cut |
|---|---|---|
| Two-pass apply on three platforms | Calendar holds (tentative only) | Interview dossier generation |
| Evidence graph over one repository plus elicited statements | Document ingestion beyond primary repository | Web research on employer sponsorship |
| Credits with trace-through and gap flagging | Multi-user support (single-user data, multi-user-shaped keys) | Account creation and credential handling |
| Autonomous inbound pipeline with staleness detection | | Any auto-submission path |
| One closed analyst loop with exploration budget | | Additional ATS platforms |
| Eligibility scoring from structured filings | | Mobile client |
| Tier-1 triage with measured tier-down rate | | Components excluded by ADR-0012 |
| | | Separate analytic warehouse |

---

## 14. Definition of Done

- [ ] Three ATS platforms fill at ≥90% on fixtures, with one clean live run each
- [ ] 100% credit coverage, reported split by attestation class
- [ ] Zero `derived` claims reach a package, asserted in tests
- [ ] Adversarial posting produces gaps and elicitation questions, not fabrications
- [ ] The no-public-artifacts profile produces a fully credited application
- [ ] One experiment resolved end to end; a second actively assigning
- [ ] Priors report intervals, not point rates; a zero-reply segment remains ranked and visible
- [ ] Only eligibility can exclude; `may_exclude` false on every prior record, asserted in tests
- [ ] Exploration budget honored and visible in the outcome log
- [ ] Inbound path runs on the adaptive schedule, with batched triage and idempotency tests
- [ ] Tier-down rate measured and reported; daily quota consumption inside free-tier ceilings
- [ ] Test suite makes zero model API calls
- [ ] `outcomes` proven append-only: update and delete denied by rule, asserted in tests
- [ ] `submit_application` unreachable from any agent path, asserted in tests
- [ ] Deploy verified from a clean project
- [ ] Architecture documented, including the asynchronous path: trigger, worker, state, artifact

---

## 15. Future Scope

Designs that are specified but deliberately not built. Recorded so the constraint is understood rather than rediscovered, and so the boundary of the current build is explicit.

### 15.1 Delegated authenticated sessions

**Trigger condition.** Required only to support a platform that gates applications behind a candidate account — Workday-class portals in particular. The three target platforms do not (Section 8.3), so nothing here is on the critical path.

**Problem.** An agent running server-side needs to act inside a session belonging to a human, without holding the human's credentials, without retaining a long-lived secret, and in a manner that is auditable and revocable.

**Approach: just-in-time authentication in an ephemeral custodial session.** Rather than storing a session for later reuse, the storage problem is removed. The agent composes and fills up to the authentication boundary, suspends the run, and requests the user. The user authenticates inside a streamed remote browser; the agent resumes in that same live session; the browser profile is destroyed when the run ends.

Four properties follow by construction rather than by policy:

| Property | Mechanism |
|---|---|
| Credential-free | No password or long-lived token is ever held; there is nothing to leak |
| Ephemeral | Browser profile exists for one run; session lifetime equals task lifetime |
| Scoped | Profile egress locked to a single domain for the run's duration, so an injection inside a borrowed session has no destination |
| Attested | Every action in the borrowed session is logged with a capture and replayable by the user |

This converts a credential-storage problem into a scheduling problem. It composes with the notification-driven interaction model: the system already contacts the user when a human is required, and this is one further reason.

**Fallback: replay bundle.** Where a streamed session is unavailable, the agent emits the composed, credited field-to-value map, and the user's own browser applies it to an already-authenticated tab. Reasoning remains server-side; authentication remains client-side; the bundle is inspectable before it is applied.

**Not specified here.** Streaming transport, profile lifecycle management, and the revocation surface. This section records the approach and its guarantees, not an implementation.

---

## Appendix A: Attestation Classes

| Class | Origin | Third-party inspectable | Artifact exists | Admissible |
|---|---|---|---|---|
| `verifiable` | User's work | Yes | Yes | Yes |
| `corroborated` | User's work | On request | Yes, privately held | Yes |
| `attested` | User's statement | No | No | Yes, labeled |
| `derived` | Model | No | No | No |

---

## Appendix B: State Transitions

| From | To | Trigger | Notes |
|---|---|---|---|
| `DISCOVERED` | `PREPARED` | Package composed | Composer output validated |
| `PREPARED` | `SUBMITTED` | Human submit | Only human-initiated transition |
| `PREPARED` | `ABANDONED` | User discard or staleness | |
| `SUBMITTED` | `ACKED` | Confirmation message | |
| `ACKED` | `SCREEN` | Scheduling or recruiter contact | Triggers calendar hold |
| `SCREEN` | `ONSITE` | Scheduling message | |
| `ONSITE` | `OFFER` | Offer message | Immediate escalation |
| Any | `REJECTED` | Rejection message | |
| `ACKED`, `SCREEN`, `ONSITE` | `GHOSTED` | Silence threshold elapsed | Time-derived; triggers follow-up draft |

---

## Appendix C: Side-Effect Classes

| Class | Definition | Agent-invocable |
|---|---|---|
| `pure` | No external effect | Yes |
| `read` | External read only | Yes |
| `write-draft` | Produces content requiring human action to take effect | Yes |
| `write-user-originated` | Persists content authored by the user | Yes |
| `write-reversible` | External effect that can be undone | Yes |
| `write-staged` | External effect that stops short of commitment | Yes |
| `human-only` | Irreversible or identity-asserting | No |

---

## Appendix D: Non-Goals

| Non-goal | Reason |
|---|---|
| Auto-submission | The human owns every irreversible action |
| Account creation, authentication, bot-challenge solving | Identity assertion; credential handling |
| Delegated authenticated sessions | Not required by the target platforms; approach recorded in Section 15.1 |
| Automated interaction with platforms prohibiting it | Terms compliance; account risk |
| Unsourced claims | No model-originated claim reaches an employer |
| Suppression by outcome history | Only externally verifiable eligibility may exclude |
| Interview dossier generation | Scope |
| Web research on employer sponsorship | Structured filings only |
| ATS platforms beyond the three targeted | Scope |
| Mobile client | Scope |
