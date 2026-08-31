# Explanations

What each completed phase actually built, in plain English, for a reader who has not read the
specification.

These are not changelogs. The commit history already records what changed file by file; these
record what now exists, why it was built that way, and what it does not yet do. The
[specification](../TalentAgent-Spec.md) says what the system must do, the
[plan](../TalentAgent-Plan.md) says in what order, and these say what is true today.

| Phase | Explanation | Status |
|---|---|---|
| 0 | [Foundations, fixtures, and the guardrail harness](phase-0-foundations.md) | Built; the corpora it once held moved to the phases that read them |
| 1 | [Two-pass apply](phase-1-two-pass-apply.md) | Built; the live runs against real postings are Phase 3 |
| 2 | [Evidence graph and credited composition](phase-2-evidence-graph.md) | Built; retired risk R2 |
| 2.5 | [Interactive demo and review surface](phase-2.5-demo.md) | Built; live Gemini agent loop behind a single-page review surface |
| 3 | What remains: the inbound pipeline, opportunity scoring and the analyst loop, deployment and acceptance | Not started |
