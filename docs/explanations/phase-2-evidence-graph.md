# Phase 2: Evidence graph and credited composition

## What this phase was for

Most generative AI tools in the job search space share a fatal flaw: hallucination. When asked to
tailor a resume or cover letter for a posting requiring unfamiliar skills, they invent claims,
inflate metrics, and generate plausible-sounding falsehoods. If an employer catches it, the candidate
is disqualified.

Phase 2 exists to retire risk R2 ([ADR-0011](../ADRs/0011-three-pillar-scope.md)): ensuring that every
claim an application makes is grounded in verifiable evidence, and that the system refuses to generate
text when evidence is missing.

The outcome of this phase is an evidence-constrained generation engine where no uncredited line can
reach an employer, backed by an immutable graph data model and a graded provenance taxonomy
([ADR-0002](../ADRs/0002-graded-attestation-classes.md)).

## What now exists

### The evidence graph data model

Candidate experience is stored not as unstructured resume text, but as a typed graph of six durable
node types:
- Artifacts: inspectable third-party work products (git commits, pull requests, published design docs).
- Statements: user-asserted claims preserved byte-identically in the candidate's own words.
- Skills: canonical technology and competency concepts.
- Metrics: quantified measurements of impact, scale, or latency reduction with explicit basis.
- Accomplishments: clustered claims linking back to their underlying evidence.
- Hypotheses: analytical assertions evaluated by the analyst loop.

Nodes connect through directed edges (`evidences`, `demonstrates`, `supersedes`), creating an unbroken
chain of custody from raw artifacts to resume bullets.

### Graded attestation classes and the quarantine boundary

Not all evidence carries the same level of independent verification. The graph classifies
accomplishments into four distinct attestation classes ([ADR-0002](../ADRs/0002-graded-attestation-classes.md)):
- `verifiable`: directly inspectable via public third-party sources (e.g. open-source pull requests).
- `corroborated`: backed by private repository or internal system artifacts.
- `attested`: directly stated by the candidate in their own words.
- `derived`: generated or inferred by an AI model.

The crucial invariant is the derived quarantine (Spec §3.4 Invariant 2, Guardrail G1). All candidate
accomplishments clustered by background sync jobs enter the graph strictly as `derived`. A composer
query choke point enforces that no `derived` accomplishment can ever be retrieved or selected by the
application composer until confirmed or stated by the user.

### Per-requirement sufficiency scoring

When evaluating a job posting's requirements against the candidate's evidence graph, the system
calculates a numeric sufficiency score between 0.0 and 1.0.

Crucially, this scoring is deterministic and computed entirely outside the model
([ADR-0008](../ADRs/0008-deterministic-field-map.md)). It evaluates skill overlap, quantitative metrics,
and attestation class strength. If the score is below the declared threshold (0.6), the composer refuses
to generate a bullet and routes the requirement to the gaps deliverable.

### The gaps deliverable and structured elicitation

Rather than guessing or inventing experience, the system treats missing evidence as a first-class deliverable:
- `FLAG`: emitted when partial evidence exists below the sufficiency threshold, highlighting the best
  available accomplishment so the candidate can decide whether to proceed.
- `ELICIT`: emitted when no supporting evidence exists in the graph, generating exactly one scoped question
  requesting specifics (timeframe, scale, and candidate's specific role relative to the team's).

When the candidate answers an elicitation question, the system promotes the statement verbatim into the
graph (Invariant 3) and creates an `attested` accomplishment. At no point does a model draft the claim.

### Credited composition and the rejection layer

During Pass 1 of the application workflow, the composer creates an `ApplicationPackage` consisting of:
- `bullets`: generated resume lines, each carrying an explicit list of accomplishment credits, the resulting
  attestation class, and linked artifact identifiers.
- `screening_answers`: answers to employer questions backed by evidence credits.
- `gaps`: the explicit list of unevidenced requirements.
- `coverage`: summary metrics breaking down the proportion of verifiable, corroborated, and attested claims.

Before a package can be saved or forwarded to the ATS form worker (Pass 2), a strict validation layer
asserts Guardrail G2: every generated line must carry at least one credit resolving to an admissible,
non-derived accomplishment in the graph. Any uncredited line or invalid credit raises an immediate rejection.

### The no-public-artifacts profile (Profile B)

A core risk addressed in this phase was whether the system only works for software engineers with public
GitHub repositories.

To prove general applicability, Profile B was constructed for a non-engineering role (product lead)
built entirely from elicited statements. The evaluation demonstrates that Profile B achieves 100%
attested coverage with zero public artifacts, proving that candidates from non-technical disciplines
receive full, credited composition without degrading into unverified hallucinations.

## Evaluation and gate results

The Spike B gate evaluated the system across two rigorous test suites:
1. Adversarial job requirements: 10 out-of-scope requirements designed to induce hallucination (e.g. quantum
   computing, blockchain smart contracts, biotech regulatory clearance). All 10 requirements were routed
   to `gaps[]` with zero uncredited claims and zero model-originated leaks.
2. Profile B purity: Composed complete application packages for non-engineering candidates, achieving
   100% attested coverage and 0% verifiable coverage.

The full numerical breakdown is recorded in the [Spike B gate record](../gates/spike-b.md).

## What was also built along the way

- Firestore operational data model and security rules: defined the six durable collections, implemented
  write ownership by component token claim, and enforced append-only immutability on the outcomes log.
- Scheduled evidence sync workflow: implemented automated GitHub artifact ingestion with persistent cursors
  and milestone-triggered retrospective elicitation.
- Tool registry expansion: wired `query_evidence`, `elicit_evidence`, and `promote_statement` into the
  tool surface under their designated side-effect classes.
