# TalentAgent Phase 2 implementation plan — handoff

Scope: milestone "Phase 2 — Evidence graph and credited composition", epic
[#19](https://github.com/sid-ak/TalentAgent/issues/19), tasks #4, #10, #20, #21, #22, #23, #24, #25,
#26, #27, #28, plus the phase explanation page. Goal: retire R2 — every generated line traces to
something the user actually said or did, and where nothing supports a requirement the system
reports a gap instead of writing around it.

This file is a handoff for another agent. It is deliberately not committed. Read it alongside
`AGENTS.md`, `docs/TalentAgent-Spec.md` §3, §5, §9.1, §10, §11, §12, `docs/TalentAgent-Architecture.md`
§5, ADR-0002, ADR-0008, ADR-0011, ADR-0012, and each task issue (`gh issue view <n>`). Nothing below
restates an issue's acceptance criteria in full — the issues remain the contract.

---

## 0. Ground rules that are easy to get wrong here

Taken from `AGENTS.md`, the user's global preferences, and project memory. Violating any of these
means rework.

- Branch: create `phase-2-evidence-graph` stacked on `phase-1-two-pass-apply` (not on `main`),
  because Phase 2 builds on Phase 1's package and store boundary. `git switch -c phase-2-evidence-graph phase-1-two-pass-apply`.
- Commit per task issue, title exactly `#19-<task>: What you did.` — e.g.
  `#19-20: Added the evidence graph node and edge types and their invariants.` Phase-level work with
  no task issue uses `#19-0: ...`.
- Never push. Never open the PR. Commits on the branch are the end state.
- No bold anywhere — not in code comments, docs, commit messages, or PR text. Headings, lists and
  backticks only.
- Docstrings on every module, class, function, fixture, and pytest hook. Module constants and enum
  members get a string literal directly after the assignment, never a `#:` comment. (While you are
  in `tests/conftest.py`, convert the existing `#:` comment above `ATS_FIXTURES` to a docstring —
  it is the one place in the repo that breaks this rule.)
- DRY is enforced in review. If a guard, query, error message, or fixture would appear twice,
  factor it in the same pass.
- Zero-budget (ADR-0012): no dependency needing a payment instrument, and the suite makes zero
  model API calls — record golden responses and replay them. The Firestore emulator is free and
  local; use a `demo-` prefixed project id so it can never touch a real project.
- Cite spec sections, guardrail ids, and ADRs in code comments and commit bodies the way Phase 1
  does (`Spec 3.4`, `G1`, `ADR-0002`).
- Every phase ships a plain-English explanation page in the MkDocs site (see §5 below).

## 1. Lessons from the Phase 1 review (PR #58) — do not repeat these

The four findings Claude raised and one theme behind them. Each maps onto something Phase 2 will be
tempted to do again.

1. Degenerate denominators must not read as success. `Completion.rate` returned `1.0` when there
   were zero fillable fields, so a halted run was recorded as 100% complete. In Phase 2 the same
   trap sits in three places: sufficiency for a requirement with no candidates (must be `0.0`, never
   vacuously high), coverage for a package with no bullets (must not be 100%), and gap recall over an
   empty expectation set. Write the degenerate case into a test before the happy path.
2. Do not spend model quota re-asking a question that was already declined. Track "offered" separately
   from "accepted" whenever a loop can revisit a unit of work. The composer's retry/repair path is
   the analogue here.
3. Every job entry point must degrade rather than crash. `GoldenResponseMissing` escaped the form
   worker's handler. `talentagent/jobs/evidence_sync.py` and `spike_b_gate.py` must catch
   `GoldenResponseMissing`, `QuotaExhausted`, `InjectionAttempt`, and their own domain failures, and
   still emit an artifact.
4. No GitHub Actions script injection. Workflow inputs and `github.*` values go through `env:` and
   are referenced as `"$VAR"`, never interpolated into a `run:` block — especially in a step that
   also holds secrets. `evidence-sync.yml` must follow `form-worker.yml`'s fixed form.
5. Theme: test through the real path, not only the unit. Several findings were invisible because the
   tests called a component directly rather than driving it through the loop that uses it. Phase 2's
   guardrail tests must enumerate the query surface and run the whole fixture suite, as the issues
   ask.
6. Keep docstrings in sync with constants (a stale "three passes" docstring beside `MAX_PASSES = 4`
   was flagged). Threshold constants in this phase — sufficiency, coverage — carry their reasoning
   in the docstring; update it when you change the number.

## 2. Decisions already taken, so you do not re-litigate them

### 2.1 Module layout

New code, following the existing convention that domain code lives in a top-level package
(`ats/`, `net/`, `state/`) and job entry points live in `jobs/`:

```
talentagent/evidence/graph.py        Node and edge types, attestation classes, the Spec 3.3
                                     schemas, and the Spec 3.4 invariants               (#20, #21)
talentagent/evidence/store.py        Graph store protocol, local JSON backend, and the
                                     composer-reachable query surface with the
                                     `derived` quarantine                               (#20, #21)
talentagent/evidence/sync.py         Ingest, classification, clustering, metric attachment,
                                     the sync cursor, retrospective elicitation trigger  (#22)
talentagent/evidence/retrieval.py    Requirement normalisation, ranking, sufficiency      (#23)
talentagent/evidence/elicitation.py  Gap contract, elicit_evidence, promote_statement     (#26)
talentagent/composer/package.py      The full Spec 5.1 package schema and its validation  (#25)
talentagent/composer/compose.py      Pass 1                                               (#24)
talentagent/composer/coverage.py     Coverage by class, credit trace-through, metrics     (#27)
talentagent/state/documents.py       Collection names, write-ownership table, the document
                                     envelope and `timeline[]` entries                    (#4)
talentagent/state/firestore.py       Firestore backends for packages and the graph         (#4)
talentagent/jobs/evidence_sync.py    Entry point for the scheduled sync                   (#22)
talentagent/jobs/spike_b_gate.py     The Spike B measurement harness                      (#28)
firestore.rules, firebase.json, .firebaserc                                               (#4)
.github/workflows/evidence-sync.yml                                                       (#22)
docs/gates/spike-b.md, docs/explanations/phase-2-*.md                              (#28, phase)
```

`talentagent/agents/composer/` and `talentagent/agents/evidence/` stay as they are: empty packages
naming the ownership boundary. Phase 1 set the precedent that executable domain code lives in a
top-level package (`ats/`), not under `agents/`. Follow it rather than splitting the difference.

### 2.2 Where the application package schema lives

Phase 1 shipped `talentagent/ats/package.py` as the Pass-2 slice (`Identity`, `Links`, `Materials`,
`ScreeningAnswer`, `ApplicationPackage`) with a docstring saying the full schema arrives with #24.
Honour that: move those models into `talentagent/composer/package.py`, extend the model with the
Spec 5.1 fields (`bullets`, `gaps`, `coverage`), and update every Phase 1 import
(`talentagent/ats/*`, `talentagent/state/packages.py`, `talentagent/jobs/*`, `tests/*`).

Do not leave a re-export shim in `talentagent/ats/package.py` — delete the file. A move is two
sided: remove and add, then verify the destination side by running the full suite and mypy.

Keep `resolve_path()` on the package (Pass 2's field maps address it by dotted path); its docstring
should say that is what it is for.

### 2.3 Firestore without a project (#4)

- Emulator only. `firebase.json` configures the Firestore emulator on a fixed port; `.firebaserc`
  pins project `demo-talentagent` (the `demo-` prefix guarantees the emulator never proxies to a
  real backend). No live project, no billing.
- `google-cloud-firestore` goes in a `firestore` optional extra in `pyproject.toml`, mirroring the
  existing `browser` extra, so the default fixture suite needs neither the library nor a JVM. Add a
  mypy override with `ignore_missing_imports` for `google.cloud.*` alongside the existing
  `playwright.*` one.
- Rules assertions cannot use the admin client — the admin path bypasses rules. Drive the emulator's
  REST API with an unsigned JWT bearer token, which is exactly what `@firebase/rules-unit-testing`
  does under the hood: `alg: none`, payload carrying `aud`/`iss` set to the project id, `sub` and
  `user_id`, `iat`/`exp`/`auth_time`, `firebase: {sign_in_provider: "custom", identities: {}}`, plus
  the component claim under test. `Authorization: Bearer owner` is the admin bypass, useful for
  seeding.
- That harness needs HTTP, and `requests`/`httpx`/`urllib.request` are banned repo-wide by TID251.
  Put the harness in `tests/firestore/emulator.py` and add one `per-file-ignores` entry in
  `pyproject.toml` with a comment saying why: this is a loopback call to a local emulator, not an
  outbound read, so G5's allowlist does not apply. Do not reach for `http.client` to slip past the
  ban — the exemption should be visible in review.
- Mark the rules tests `@pytest.mark.network` (the existing marker exempts them from the socket ban)
  and skip them with a clear reason when `FIRESTORE_EMULATOR_HOST` is unset, so a local run without
  firebase-tools still passes.
- CI: a new `rules` job in `.github/workflows/ci.yml` — `actions/setup-node`, `npm i -g firebase-tools`,
  then `firebase emulators:exec --only firestore "uv run pytest -m network -v"`. Java is present on
  `ubuntu-latest`.
- Per-test isolation: each test gets its own collection prefix or clears the emulator between tests
  via its REST clear endpoint. Provide one shared seeding helper the fixture corpora reuse (#10 and
  #28 both need it) rather than seeding ad hoc per test.

### 2.4 Ordering

Issue numbers do not force execution order; the epic's dependency notes do. Recommended sequence,
one commit each:

1. #20 then #21 — the node schemas and the quarantine. The Firestore rules in #4 validate these
   shapes, and Spec 3.3 already fixes them, so building the Python models first means the rules are
   written once against something real.
2. #4 — collections, documents, rules, emulator harness, Firestore backends.
3. #10 — the two profiles, seeded through #4's helper.
4. #22, #23, #24, #25, #26, #27 in that order.
5. #28 — the gate, last, because it measures everything above.
6. `#19-0` — the phase explanation page, nav entry, `docs/explanations/index.md` status row, and any
   AGENTS.md repository-layout update the new directories require.

If you prefer the epic's literal order (#4 first), write the rules against Spec 3.3 directly and
accept that #20 will follow them. Either is defensible; do not do it half way.

## 3. Task-by-task

Each entry gives the design decisions worth fixing in advance. The issue holds the full acceptance
criteria; verify against the issue, not against this summary.

### #20 — Evidence graph: node types, edge types, invariants

`talentagent/evidence/graph.py`, `talentagent/evidence/store.py`.

- Enums, each member carrying a docstring: `NodeType` (ARTIFACT, STATEMENT, ACCOMPLISHMENT, SKILL,
  METRIC), `ArtifactSubtype` (COMMIT, PR, DOC, DESIGN, TICKET, COURSE, CALENDAR_EVENT), `EdgeType`
  (EVIDENCES, DEMONSTRATES, QUANTIFIES, SUPERSEDES).
- Edge legality is structural, not documented: give `EdgeType` a table of permitted
  `(source NodeType, target NodeType)` pairs from Spec 3.1 and reject an illegal edge at construction.
- Pydantic v2 models with `extra="forbid"` and frozen where nothing mutates: `Artifact`, `Statement`,
  `Skill`, `Metric`, `Accomplishment`. `Accomplishment` is the Spec 3.3 shape and must cover both
  the artifact-backed and statement-backed examples verbatim — both round-trip without loss is an
  acceptance criterion, so put both JSON documents in the fixtures and assert it.
- Invariant 1, non-empty provenance: `evidence` is required and non-empty, enforced by the model and
  again in `firestore.rules` (#4).
- Invariant 3, verbatim retention: `statement.raw` is stored exactly as written and never normalised.
  Be explicit about pydantic settings that would silently break this (no `str_strip_whitespace`, no
  coercion). Test with quotes, newlines, non-ASCII, and leading/trailing whitespace, byte-comparing
  after a write-and-read cycle through both backends.
- `SUPERSEDES`: superseded accomplishments are excluded from retrieval but readable in history. Model
  this as two query paths on the store (`active()` vs `history()`), not as a delete.
- Store: a `EvidenceStore` protocol plus a local JSON backend, mirroring how `state/packages.py`
  paired a protocol with `LocalPackageStore`. Queries the composer needs: by skill, by period, by
  attestation class, and traversal to supporting evidence.

### #21 — Attestation classes and the derived quarantine

- `AttestationClass` enum (VERIFIABLE, CORROBORATED, ATTESTED, DERIVED) with the Appendix A columns
  as properties — `admissible` is false only for DERIVED. Class is required at write time and set by
  the component that created the node; there is no inference path and no default.
- The quarantine is one choke point, not a filter repeated per query. Suggested shape: a
  `@composer_query` decorator that both registers the method name in a module-level
  `COMPOSER_QUERIES` tuple and asserts no DERIVED node is in the result. The #21 acceptance
  criterion is that the assertion enumerates the query surface, so the guardrail test iterates
  `COMPOSER_QUERIES` and calls each against a graph seeded with derived nodes — it then fails
  automatically when someone adds a query and forgets.
- A separate, deliberately non-composer-reachable `quarantined()` query feeds the confirmation
  surface.
- Promotion produces an `attested` Statement in the user's words. The promotion function takes the
  user's text as an argument and never copies the derived node's claim — assert that a promoted
  node's `statement.raw` differs from the derived phrasing when the user typed something different,
  and that no code path passes the model's text in.
- G1 test in `tests/guardrails/`: a derived node cannot reach a package by any route, run over the
  whole fixture suite. `tests/guardrails/test_pending_invariants.py` already holds placeholders for
  the not-yet-built guardrails — move G1 and G2 out of it as they become real.

### #4 — Firestore data model, security rules, emulator harness

See §2.3. Additionally:

- `talentagent/state/documents.py`: the six collection names (`applications`, `evidence_graph`,
  `packages`, `hypotheses`, `assignment_rules`, `outcomes`), the Architecture §5.1 write-ownership
  table as data (path pattern to writer claim), a `TimelineEntry` model, and a document envelope that
  makes "every mutation appends to `timeline[]`" mechanical rather than remembered.
- `firestore.rules`: write-ownership keyed on a component claim; schema validation inside the rules
  (a write missing a required field is refused server-side); `outcomes` create-only — update and
  delete denied for every principal including the owner.
- Rules tests assert per path and per operation, not per component — one writer succeeding on its own
  path and being denied on each other path, and update/delete denied on `outcomes` separately.
- Add a `FirestorePackageStore` implementing the existing `PackageStore` protocol beside
  `LocalPackageStore`, and the equivalent graph backend. The local backends stay: they are what keeps
  the offline suite runnable.

### #10 — Evidence seed and the no-public-artifacts profile

`tests/fixtures/evidence/`.

- Profile A: one real public repository ingested into artifacts — commits, pull requests, documents.
  Anonymise before commit (the repository is public; see Architecture §6.4). Store the GitHub API
  responses as fixtures so #22's ingest is exercised without network.
- Profile B: a non-engineering role built entirely from elicited statements. Assert it contains zero
  `artifact_backed`/`verifiable` nodes rather than assuming it, so Spike B's fourth criterion measures
  what it claims to.
- Golden model responses recorded for both profiles covering tier-1 and tier-2 calls for every
  fixture, so Phase 2's tests make no API calls.

### #22 — Evidence sync

- Ingest through `talentagent.net.fetch` (`api.github.com` is already on the allowlist); inject the
  transport in tests, as Phase 1 does. Everything returned is `UntrustedText` — read it with
  `.as_data()` into a model call's `data`, never its `prompt` (G7).
- Classification is mechanical: `verifiable` where the artifact resolves to a source a third party can
  inspect, `corroborated` where the user holds it privately. Not a model call (ADR-0008).
- Clustering output is always `derived`, with no exception path. Enforce structurally: a
  `candidate_accomplishment()` factory that hard-codes the class and takes no class parameter, so
  there is nothing to pass.
- Metric attachment only where an artifact states one; `basis` records how it was obtained.
- Incremental: a persisted cursor per source. The acceptance test asserts a second run ingests
  nothing new and issues fewer reads.
- Elicitation trigger 2 (project close or milestone) emits exactly one scoped question, reusing #26's
  question construction — do not write a second question builder.
- `.github/workflows/evidence-sync.yml` on a schedule, with the `env:`-passing discipline from §1.4
  and a step that still uploads its artifact when the job fails.

### #23 — Retrieval with per-requirement sufficiency

- `normalise_requirement()` is deterministic where the posting is structured; model use is a
  narrow, logged fallback (ADR-0008).
- Sufficiency is computed outside the model from candidate strength and coverage, and is
  reproducible: the same graph and requirement produce the same figure. Pure function, no clock, no
  set iteration order.
- Declare the threshold as a named constant with its reasoning in the docstring, configurable through
  a small config object rather than a magic number at three call sites.
- `derived` candidates are excluded before ranking, at the store query, not filtered afterwards.
- A requirement with no candidate scores exactly `0.0` and produces a gap. This is the degenerate
  case from §1.1 — test it first.
- Wire the real implementation into `talentagent/tools/catalog.py`, replacing the `query_evidence`
  placeholder (side-effect class stays `read`).

### #24 — Constrained composition, Pass 1

- Inputs: posting requirements, retrieved evidence per requirement, active assignment rules. Nothing
  else is admissible.
- The model selects and phrases; it does not introduce. Enforce by construction: the model may only
  reference candidate ids from the set it was handed, and the returned id is validated against that
  set before it becomes a credit. Credits are assigned from the retrieval result, never parsed out of
  free text.
- Tier-2 calls through `ModelClient`, recorded as golden fixtures. Replay must make the whole
  composition deterministic — same inputs, same package.
- Requirements below the sufficiency threshold route to the gap contract and produce no bullet.
- The active assignment rule is recorded on the package and on the outcome row (Spec 7.2), so an
  exploration assignment stays distinguishable later.
- The composed package is written to `packages`, which the composer exclusively owns (single-writer,
  Spec 2.2).

### #25 — Package schema validation and credit enforcement

- `talentagent/composer/package.py` holds the Spec 5.1 schema and its validation. Rejection, not
  flagging: a line without a valid credit, or backed by a `derived` node, fails validation.
- Credit resolution is checked rather than assumed — each credit must resolve to an existing node of
  an admissible class, which means validation takes the graph, not just the package.
- Validation failure is a composer failure with a legible reason, surfaced through `ESCALATE`
  (`talentagent/tools/escalation.py` already models this) rather than by emitting a partial package.
- The same structural checks go into `firestore.rules`, so a package cannot be written around the
  application layer.
- G2 guardrail test: no path produces a package with an uncredited line, over the whole fixture suite.

### #26 — Gaps and elicitation

- Gap model per Spec 5.3: `requirement_id`, `text`, `best_available`, `sufficiency`, `action`
  (`FLAG` where partial evidence exists below threshold, `ELICIT` where none does), `question` only
  for `ELICIT`.
- A questionnaire must be unproducible, not merely unproduced: `elicit_evidence` returns a single
  `Question` object rather than a list. Type-level impossibility beats a length check.
- `elicit_evidence` is `write-draft` and has no code path that writes a Statement — assert it through
  the tool registry, as the issue asks.
- `promote_statement` is `write-user-originated`: the user's raw answer becomes a Statement node and
  an `attested` Accomplishment, raw text byte-identical to what they typed.
- Questions request specifics — quantity, timeframe, and the user's role relative to the team's.
  Build them from a template with those three slots so the shape is guaranteed rather than hoped for.
- A model-composed answer is written `derived` and quarantined, with no promotion path that skips the
  user.
- Replace both catalog placeholders with the real implementations.

### #27 — Coverage by class and credit trace-through

- Coverage is per class plus a total, and no code path produces a single scalar. Make that structural:
  the `Coverage` model requires the per-class fields, and nothing returns a bare float.
- The empty-package degenerate case: a package with no bullets is not 100% covered. Decide and
  document what it reports (0.0 with an explicit "nothing composed" reason is the honest answer) and
  make the gate treat it as a failure, not a pass.
- Credit trace-through resolves in one step to a viewable source: a public artifact link, a private
  artifact reference, or the user's verbatim statement. A statement-backed bullet displays the raw
  text alongside the generated line, so drift is visible (Spec 3.4 invariant 3).
- Metrics for Spec 12: credit coverage by class, `derived` leakage (must read zero), graph growth per
  application.

### #28 — Spike B gate

- Adversarial posting suite in fixtures: requirements the graph genuinely cannot support, requirements
  phrased to invite embellishment, and postings containing injection attempts (which must be logged
  and refused by `wrap_untrusted`, never acted on — G7).
- `talentagent/jobs/spike_b_gate.py` mirrors `spike_a_gate.py`: runs the full apply path over both
  profiles, prints a markdown table, exits non-zero on failure, and is reproducible offline. Reuse the
  gate-report shape rather than inventing a second one.
- Gap recall is measured against a labelled expectation committed with the adversarial suite —
  requirements correctly flagged versus written around.
- A `spike-b` job in `ci.yml` and `pytest -m slow` assertions pinning the criteria, following the
  `spike-a` precedent.
- `docs/gates/spike-b.md` with the figures and an honest statement of what the numbers do and do not
  establish, added to the `mkdocs.yml` nav under Phase gates.
- Criteria: 100% credit coverage split by class; zero `derived` leakage; every adversarial requirement
  produces a gap or a question and none produces a bullet; the no-public-artifacts profile produces a
  fully credited application whose coverage is entirely `attested` and labelled as such.

## 4. Cross-cutting checklist before each commit

- `uv run ruff check . && uv run ruff format --check . && uv run mypy` clean.
- `uv run pytest` green, including `-m guardrail` and `-m slow`.
- Docstring on every new module, class, function, fixture, and test; constants and enum members carry
  theirs after the assignment.
- Diff scanned for repetition — shared fixtures, one question builder, one gate-report shape, one
  seeding helper.
- Tick the task in epic #19 (`gh issue edit`/`gh issue comment` as appropriate) rather than only
  closing the issue.

## 5. Phase-closing work (`#19-0`)

1. `docs/explanations/phase-2-evidence-graph-and-composition.md`: plain English, for a reader who has
   not read the spec. What now exists and why it matters — the graph, graded provenance and why
   user-asserted evidence is admissible without making a credit meaningless, the quarantine, why a gap
   is a deliverable, and what the phase does not yet do. Not a changelog.
2. Add it to the `nav` in `mkdocs.yml` under Explanations, and update the status row for Phase 2 in
   `docs/explanations/index.md`.
3. Update `AGENTS.md` §7 repository layout for the new top-level directories (`talentagent/evidence/`,
   `talentagent/composer/`) and, if the rules land, the `firestore.rules` entry.
4. If any Phase 2 decision makes the spec or architecture untrue, update it in the same change, or
   write an ADR if it is a new load-bearing decision.
5. `uvx --with-requirements requirements-docs.txt --from mkdocs mkdocs build --strict` must pass — it
   fails on a broken internal link or an unresolvable reference.

## 6. PR text (draft only, do not open it)

The user opens PRs themselves. When asked, use the `pr-draft` skill against
`.github/pull_request_template.md`: title `[phase-2] Evidence graph and credited composition`, a
summary leading with the non-obvious parts (the quarantine choke point, credits assigned from the
retrieval result rather than parsed from model text, rules-level validation mirroring the schema, the
emulator harness without a Firebase project) with commit short-hashes cited inline, command-first
verification, and the invariants list with any line this change cannot affect deleted rather than left
unticked.
