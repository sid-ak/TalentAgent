# AGENTS.md

Working agreement for anyone — human or coding agent — making changes in this repository.

TalentAgent is an event-driven multi-agent system that runs a job search as a long-running
workflow. Read [`docs/TalentAgent-Spec.md`](docs/TalentAgent-Spec.md) before changing behaviour;
it is the contract, and this file only tells you how to work against it.

---

## 1. Orientation

Read in this order. Each answers a different question, and none of them restates another.

| Document | Answers |
|---|---|
| [`docs/TalentAgent-Why.md`](docs/TalentAgent-Why.md) | Why the product exists and what the category gets wrong |
| [`docs/TalentAgent-Spec.md`](docs/TalentAgent-Spec.md) | Agent contracts, schemas, coordination, tool surface, guardrails, scope |
| [`docs/TalentAgent-Architecture.md`](docs/TalentAgent-Architecture.md) | Where things run, what they may reach, how work propagates |
| [`docs/TalentAgent-Plan.md`](docs/TalentAgent-Plan.md) | The phase breakdown that GitHub milestones and issues mirror |
| [`docs/ADRs/`](docs/ADRs/README.md) | Why each load-bearing decision was taken, and what it cost |

The specification is the source of truth for behaviour. The architecture document is the source of
truth for topology. If a change makes either untrue, update that document in the same change — a
stale spec is worse than no spec, because it is trusted.

Spec section numbers are stable and are cited throughout the issues (`Spec §5.2`, `G3`,
`ADR-0008`). Cite them the same way in commits, PRs, and code comments; it is how a reader gets
from a line of code back to the reason it exists.

---

## 2. The invariants you may not quietly break

These are guardrails, not preferences (Spec §10). Each is enforced in the policy layer and asserted
in tests. If a change appears to require relaxing one, that is a specification change and an ADR,
not a code change.

| # | Invariant | Where it lives |
|---|---|---|
| G1 | No model-originated claim reaches an employer | `derived` nodes barred from composer selection; schema validation |
| G2 | No generated line without a credit | Package schema validation |
| G3 | No irreversible autonomy — submit, send, accept, decline are human-only | Tool registry side-effect classes (Spec Appendix C) |
| G4 | No suppression by self-derived signal | `may_exclude` is `false` on every prior record |
| G5 | No prohibited automation | Permitted-domain allowlist in the fetch wrapper |
| G6 | No credential handling | No account-creation or password-entry path exists |
| G7 | Untrusted content is data, never instruction | Postings, mail, and ATS pages enter as data fields |

Three consequences that catch people out:

- `submit_application` must remain unreachable from every agent path. A test asserts this. Do not
  add a code path that a future refactor could make reachable.
- Never write a prompt instruction where a schema check belongs. Guardrails that live in prompt
  text are not guardrails.
- The `outcomes` collection is append-only by Firestore security rule. Corrections append; they do
  not rewrite (Spec §11).

---

## 3. Structural rules that shape the code

Four properties of the design constrain how code is organised. They are not stylistic.

Single-writer per field (Spec §2.2, ADR-0007). Exactly one agent writes each field. Agents never
call one another; all coordination is through durable state. If you need agent A to influence agent
B, write state that B reads — the analyst's assignment rules are the one existing example, and they
work exactly this way.

Derived state, never entered (ADR-0005). Application state is computed from observed inbox and
calendar events. Do not add a code path or a UI control that lets a user type a pipeline state.

Deterministic first, model last (ADR-0008). Thread attribution, ATS field resolution, and posting
parsing are retrieval and mechanical problems. Solve them deterministically and fall back to a model
only on failure, in a narrow and logged path. A model call that could have been a lookup is a defect
in both cost and reliability.

At-least-once delivery (Spec §8.6). Every event-driven write is idempotent, keyed on
`evidence_message_id`, behind the `lastHistoryId` cursor. Assume handlers will be re-run.

---

## 4. The zero-budget constraint

Recorded once in [ADR-0012](docs/ADRs/0012-zero-budget-constraint.md). It is a hard constraint, not
a preference: there is no billing account and none will be created.

Practically, this means:

- Do not introduce a dependency that requires a payment instrument. Cloud Run, Pub/Sub, Cloud
  Scheduler, Cloud Storage for Firebase, and BigQuery are deliberately absent.
- The Gemini Flash daily quota (250 requests) is the tightest margin in the system, at roughly 2×
  headroom. Development burns it faster than operation does.
- Therefore: the test suite makes zero model API calls. Model outputs are recorded once as golden
  fixtures and replayed. A test that hits a live model is a bug, and CI asserts against it.
- Classification runs on Flash-Lite (tier 1), which carries four times the allowance. Only judgment
  work earns tier 2 (Spec §9.2).

The repository is public so that Actions minutes stay unlimited. No secret may ever be committed,
and fixtures must contain no personal data — the mail corpus and evidence seed are anonymised before
they land.

---

## 5. Working conventions

### Docstrings

Every module, class, and function gets a docstring, in core and test files alike, including fixtures
and pytest hooks. A test's docstring states what behaviour it pins; a fixture's states what it
provides. One line unless the why is non-obvious. This is enforced in the linter.

Module constants and enum members get one too, written as a string literal directly after the
assignment — never as a `#:` comment. The comment form reads the same in the source and is invisible
to the documentation site, so the reasoning it carries silently fails to publish:

```python
MAX_INVOCATIONS = 12
"""Most invocations one run may make. A form needing more has a map problem."""
```

### Tests

Deterministic, offline, fixture-driven. Phase 0 exists precisely so that no agent work begins before
the fixtures do (Spec §13.2). When you add behaviour, add the fixture that pins it.

Guardrail assertions are a distinct suite. They are not unit tests of a component; they are
assertions that a whole class of behaviour is impossible.

### Don't repeat yourself

The moment logic would appear a second time — the same guard, query, setup, or error message —
factor it into one shared place in the same change. Scan the diff for repetition before you finish.

### Prose in this repository

Documents are written to be understood by a reader with no background in the domain, while still
rewarding one who has it. Avoid a clipped or condescending register.

Keep each fact in exactly one place: what a thing does belongs in the main body of a document, why
it was chosen belongs in an ADR, and how it works internally belongs in a deep-dive section. Link
between them rather than restating.

Do not use bold. Use headings, lists, and backticks for structure and emphasis.

### Git

Committing is authorised in this repository, which is a deliberate exception to the usual
leave-it-staged convention. Pushing is not: the human pushes.

One branch per phase, named for it — `phase-1-two-pass-apply`. A phase branch that builds on an
earlier phase is stacked on that phase's branch rather than on `main`. Nothing is committed directly
to `main`.

One commit per feature, which in practice means one commit per task issue completed. Commit titles
take a fixed form so history maps one-to-one onto the tracker:

```
#<epic-issue>-<task-issue>: What you did in the task.
```

For example `#11-12: Added the field-map schema and the deterministic resolver.` Phase-level work
with no task issue of its own uses `0` as the task number — `#11-0: ...`.

---

## 6. Issues, phases, and milestones

Work is tracked as GitHub issues, grouped into six phases that mirror
[`docs/TalentAgent-Plan.md`](docs/TalentAgent-Plan.md). Each phase is a milestone and has one epic
issue holding the task checklist.

| Phase | Milestone | Retires |
|---|---|---|
| 0 | Foundations, fixtures, and the guardrail harness | R6, and the precondition for every other phase |
| 1 | Two-pass apply — deterministic execution | R1, Spike A |
| 2 | Evidence graph and credited composition | R2, Spike B |
| 3 | The autonomous inbound pipeline | R4, Spike D |
| 4 | Opportunity scoring and the analyst loop | R3 and R5, Spikes C and E |
| 5 | Review surface, deployment, and acceptance | Definition of Done |

Ordering is by risk retired, not by feature area (ADR-0011). Phases 1 and 2 run first and in that
order because they carry the two risks that would reshape the system if they could not be retired.

Labels: `phase-0` … `phase-5` locate work in the plan; `epic` marks the phase tracking issue; the
remaining labels name the component (`ats-execution`, `evidence`, `composer`, `pipeline`, `analyst`,
`scoring`, `review-ui`) or the kind of work (`infra`, `docs`, `testing`, `fixtures`, `guardrail`).

When you finish a task, tick it in the epic rather than only closing the issue — the epic is what a
reader looks at to see where the phase stands.

When you finish a phase, write `docs/explanations/phase-<n>-<slug>.md`: a plain-English account of
what now exists and why it matters, for a reader who has not read the specification. Add it to the
`nav` in `mkdocs.yml`. It is not a changelog of files touched — the commit history already is one.

---

## 7. Repository layout

```
docs/                      Specification, architecture, plan, ADRs, diagrams (the MkDocs site)
  ADRs/                    Numbered decision records; README.md is the index
  diagrams/                Rendered SVGs; mermaid source is inlined in the documents
.github/workflows/         CI and the documentation deployment
mkdocs.yml                 Site configuration; nav is explicit, so new pages must be added
```

Everything below the documentation is unbuilt and arrives phase by phase. Where a phase introduces a
new top-level directory, the epic issue names it.

---

## 8. Documentation site

The `docs/` tree is published to GitHub Pages by `.github/workflows/docs.yml`.

1. `pip install -r requirements-docs.txt`: installs MkDocs and the Material theme.
2. `mkdocs serve`: live-reloading preview on `http://127.0.0.1:8000`.
3. `mkdocs build --strict`: what CI runs; it fails on a broken internal link or an unrecognised
   reference, so run it before you finish.

Adding a prose page means adding it to the `nav` in `mkdocs.yml`. Mermaid blocks render natively
through the superfences configuration — write them as ```` ```mermaid ```` fences and do not add a
JavaScript diagram library.

The Code reference section is generated, not written. `scripts/gen_ref_pages.py` walks the package
on every build and emits one page per module, so a module added in a later phase documents itself
with no nav edit — which is the point, and the reason a change under `talentagent/` triggers the
docs workflow. The pages are virtual, so there is no generated tree in version control to fall out
of step with the source.

mkdocstrings reads the source statically through griffe, so the package is not installed to document
it and the docs build stays independent of the runtime dependencies. Nothing is filtered out:
private helpers and operator methods are part of how a component works, and this is an internal
reference rather than a published API.
