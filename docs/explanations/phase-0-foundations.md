# Phase 0: Foundations, fixtures, and the guardrail harness

## What this phase was for

Every later phase writes an agent. Phase 0 existed to make sure that when one did, its tests would
be fast, deterministic, and free — and that the boundaries the whole product depends on would be
enforced by code rather than by good intentions.

That precondition rule is stricter than it first sounds. It does not just mean "have some tests
ready" — it means a system whose tests hit live models and live forms is neither deterministic nor
affordable under the free-tier quota the project runs on
([ADR-0012](../ADRs/0012-zero-budget-constraint.md)). Phase 0 is the phase where that stops being an
aspiration and becomes something a CI run actually checks.

## What now exists

### A repository that lints and tests itself

The project started as documentation only. Phase 0 laid down the source layout every later phase
adds to, plus two lint rules that are load-bearing rather than stylistic: every module, class,
function, and test must carry a docstring, and nothing outside one named file may import an HTTP
library directly. Both are enforced by the linter, not by review — importing `requests` from
anywhere else fails the build.

Continuous integration runs four checks split so a failure is legible from the check list: lint and
format, type check, unit tests, and the guardrail suite, described below. A dependency lockfile
keeps CI resolving exactly what was verified locally.

### A test suite that cannot reach the network

This is the fixture that everything else in the project leans on. The socket layer is patched to
raise during tests, so a test cannot reach a live model even by accident — the ban is structural, not
a convention someone could forget. Every AI response the system might need is recorded once and
replayed from a fixture, keyed on a stable hash of the tier, prompt, data, and schema requested. A
missing recording raises immediately, naming the command that would record it, so a contributor who
trips it does not have to read the source to recover.

### A model client with two tiers and a paper trail

Every model call in the system goes through one client, so which tier a call uses and how much quota
it consumes are properties of the system rather than habits of each caller. The tier is chosen at the
call site and recorded, never guessed from the prompt — because the tiering claim is a measured one:
the cheaper tier carries four times the daily allowance of the other, which is the entire reason the
highest-volume work is routed there ([ADR-0006](../ADRs/0006-two-tier-model-routing.md)). A quota
ledger makes that consumption a number the system can read, not one it estimates after the fact.

Running out of quota and hitting a rate limit are treated as different problems on purpose: a rate
limit backs off and retries within the run, while exhausting the daily quota stops retrying entirely
and waits for tomorrow, because retrying it would burn what little headroom is left.

### A tool registry that makes the submission boundary structural

Every tool the system can call declares how consequential it is at the moment it is registered — a
tool with no declared side-effect class cannot be registered at all, so a class can't be added later
once someone wants a tool to do more. Six of the seven side-effect classes are agent-invocable; the
seventh, `human-only`, is not, and the enforcement is structural rather than a permission check: the
one function an agent uses to get its tools refuses to hand back a `human-only` one at all, so there
is no code path left to route around.

This is also where the guardrail suite lives. It runs as its own CI check, deliberately separate from
the unit tests, because these tests assert that a class of behaviour is *impossible* rather than that
one case works — walking every agent's entry points and proving none of them reach a human-only tool,
for instance, rather than checking a single call. Three of the seven guardrails are held as expected
failures naming the future work that will make them pass, so the suite is a complete map of the
project's invariants from day one, rather than growing invariants only as their code lands — which is
how one goes unnoticed until it's missing.

### A fetch wrapper that treats the internet as hostile

Two separate guardrails live in this one component. The permitted-domain allowlist exists because
there is no network-level egress control available on the platforms this project runs on, so the
control had to move into application code, and the code says plainly that this is a real weakening
compared to an infrastructure-level control rather than pretending it's equivalent. The list of
allowed platforms is a data file, so adding one is a one-line reviewable change, and platforms whose
terms prohibit this kind of automation are simply absent from it.

The second guardrail is carried by a type, not a habit: everything this wrapper returns is untrusted
text whose default string conversion is redacted, so an accidental attempt to interpolate fetched
content straight into a prompt can't leak it — getting the raw content back requires an explicit,
reviewable call. Content that looks like a prompt-injection attempt halts the fetch outright rather
than continuing on a best-effort basis.

### Twelve offline test forms

Application forms for the three job platforms the project targets, structurally faithful
reproductions rather than captures of real postings — because developing against a live employer's
form would make every iteration a real request against a real posting, with no two runs comparable.

The interesting cases are the employer-authored custom questions, which every platform names with an
index or an opaque, unpredictable identifier rather than anything stable. The fixtures mark those
fields as deliberately unmapped, because a field a map cannot know about in advance is meant to miss
visibly — that honest miss is the input later phases build a bounded fallback around
([ADR-0008](../ADRs/0008-deterministic-field-map.md)), not a defect to paper over. A separate hygiene
test scans the whole fixture tree for anything that looks like a real email or phone number, because
the repository is public and that makes it a publication check, not a tidiness one.

## What was deliberately left for later

Phase 0's scope is everything that has to exist before any agent can be written — not everything the
project will eventually need. The plan's precondition rule is that a corpus must precede the single
phase that reads it, not that every corpus precede everything
([Plan §1](../TalentAgent-Plan.md#1-how-the-phases-are-ordered)). A sample mail corpus, two example
evidence profiles, a log of past application outcomes, and the database layer that would hold them
are each read by exactly one later phase and nothing before it, so they now sit at the start of the
phase that actually needs them rather than waiting here for a consumer that doesn't exist yet.
Nothing was dropped; each one moved to where it is first used.

## What this phase proves

Phase 0 has no gate of its own — it produces no forms filled or applications sent, so there is no
outcome to measure. What it proves is narrower and structural: `mkdocs build --strict` and the full
test suite are green in CI, the test suite makes zero model API calls (asserted, not assumed), and
`submit_application` is unreachable from every agent's tool path (also asserted). Everything Phase 1
reports — a form filled deterministically, a model that only ever sees what it's allowed to see, a
run that halts before it can submit anything — rests on those three assertions holding.
