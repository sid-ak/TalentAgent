<!--
Title format: [<module>] <Title> — e.g. [ats] Add the deterministic field-map resolver.
A phase branch uses its phase as the module: [phase-1] Two-pass apply.
GitHub cannot prefill the title from a template, so set it by hand.
-->

## Summary

<!--
Lead with what is novel or non-obvious, not the scaffolding. Cite commit short-hashes
inline, e.g. (3b722d9), so each claim is traceable to the change that made it.

Say why a non-obvious choice was made, not only what changed — a reviewer can read the
diff for what. Skip a separate "Changes" section; if the summary is doing its job, a
restatement of the diff adds nothing.

Where a decision record or a specification section governs the change, name it: the
reviewer's first question is usually whether the change is consistent with one.
-->

## Verification

<!--
A numbered list, each item leading with the exact command in backticks, then a colon and
one short clause on what it does or what to expect. Nest related commands under a parent
step. Replace the placeholders below with what you actually ran.
-->

1. `uv run ruff check . && uv run ruff format --check . && uv run mypy`: lint, format, and
   strict types, clean.
2. `uv run pytest`: the whole suite, including the guardrail assertions.
    1. `uv run pytest -m guardrail -v`: G1 to G7 on their own, as CI reports them.
    2. `uv run pytest -m slow`: the phase gates.
3. `uvx --with-requirements requirements-docs.txt --from mkdocs mkdocs build --strict`: the
   documentation site, including the generated code reference.

## Invariants

<!--
Restated from AGENTS.md deliberately: this is where they actually get checked, and a
reviewer will not open AGENTS.md to remember them. Delete any line this change cannot
affect rather than leaving it unticked.
-->

- [ ] Guardrails are enforced in the policy layer and asserted in tests, never in prompt text.
- [ ] `submit_application` is unreachable from every agent path (G3).
- [ ] No generated line reaches a package without a credit, and no `derived` node is selectable
      (G1, G2).
- [ ] Only eligibility may exclude an opportunity; `may_exclude` is false on every prior (G4).
- [ ] Every outbound read goes through the fetch wrapper and its allowlist (G5).
- [ ] Third-party text enters as data, never as instruction context (G7).
- [ ] Exactly one agent writes each field, and no agent calls another.
- [ ] Application state is derived, never entered.
- [ ] Event-driven writes are idempotent under re-run.
- [ ] A model call was not used where a deterministic lookup would do.
- [ ] The test suite makes zero model API calls.
- [ ] No new dependency requires a payment instrument, and no secret is committed.
- [ ] Every module, class, function, fixture, and test has a docstring; constants and enum
      members carry one after the assignment rather than a `#:` comment.
- [ ] Markdown added here uses no bold, and states each fact in exactly one place.
- [ ] The specification, architecture, or a decision record was updated where this change made
      one of them untrue.

Closes #
