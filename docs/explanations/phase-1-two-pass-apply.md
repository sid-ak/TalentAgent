# Phase 1: Two-pass apply

## What this phase was for

There is one question this phase existed to answer, and the whole project was arranged so it would
be answered early: can a program reliably fill in a job application form on somebody else's website?

That sounds mundane. It is the hardest thing the system does, and it is the thing every competitor
avoids. Volume bots fill forms badly and submit them anyway; generators produce text and leave the
form to you. Filling a real employer's form correctly, then stopping, is the capability nobody
offers — so the plan puts it first, while there is still time to respond if the answer is no
([ADR-0011](../ADRs/0011-three-pillar-scope.md)).

The answer, on the evidence available so far, is yes. Every field on every test form gets filled,
and nothing gets submitted.

## What now exists

### A form-filler that does not use a model to find the fields

The obvious way to build this is to hand an AI a browser and the application, and let it work the
form out. That design was rejected, and the reason is worth understanding because it shapes
everything here.

Filling in a form is really two different jobs. One is deciding what to say — a judgement about the
applicant's experience. The other is deciding where to put it — finding the right box on the page.
The first genuinely needs a model. The second is a lookup, and giving it to a model makes it slower,
more expensive, non-deterministic, and impossible to test without hitting a real employer's website
every time you change a line ([ADR-0008](../ADRs/0008-deterministic-field-map.md)).

So the two jobs are separated. Where things go is decided by a field map: a plain list, one per
platform, saying "the box labelled Email gets the applicant's email address". Adding a field is a
one-line change to a data file, with no code involved.

Because the map identifies a box in more than one way — by its internal name, by its visible label,
and by its accessibility label — it survives the small cosmetic changes these sites make constantly.
If a platform renames a field internally, the label still finds it. If they reword the label, the
internal name still finds it.

### An honest account of what it could not fill

Most of a form is standard: name, email, phone, resume. But employers add their own questions, and
those are the interesting ones — "how many years of Kubernetes have you run in production?" Those
questions carry no stable identity at all. On all three platforms they are numbered or given a
random identifier, so no map can know them in advance.

The system does not guess at them, and it does not pretend they do not exist. It reports them as
unfilled, with the reason, and hands only those to the model. Four different reasons are tracked
separately, because they mean genuinely different things: nothing matched, the map deliberately
declined, the map matched but the applicant's package had nothing to put there, or the field is not
visible yet.

That last distinction has teeth. The measurement of how well the system did is built from those
reasons, so a field quietly skipped would inflate the score. Skipping is not possible: every field
on the form ends up in the record with an outcome.

### A deliberate refusal to answer some questions

Greenhouse forms end with voluntary questions about the applicant's gender, ethnicity, veteran
status, and disability. The map refuses these on purpose.

Nothing in the applicant's evidence answers them. The applicant may decline to answer at all, which
is the point of the questions being voluntary. And an agent filling them in would be asserting
something about a person that the person did not say — which is the exact failure the whole product
is built to avoid.

They are refused by an explicit rule rather than simply going unmatched, and that distinction
matters more than it looks. Unmatched fields are what get passed to the model to answer. Refused
fields never are. A test asserts that the model is never even offered them.

### A narrow, bounded use of AI

Custom questions do get answered by a model, within four bounds that each close a specific hole.

It only ever sees questions the map could not place — never a field the map filled, and never one
the map refused. It sees the question text and the applicant's own composed application, and never
the raw web page, so a hostile posting cannot smuggle instructions in. If it is not confident, the
field is left empty rather than filled with a guess, on the reasoning that a visibly unanswered
question is more useful than a confidently wrong answer. And there is a hard cap on how many
questions one run may ask, so a form that has drifted out of step with its map stops loudly instead
of quietly burning through the free-tier AI quota, which is the tightest resource constraint in the
whole design.

Every answer the model gives is recorded with its confidence and shown separately in the review, so
you can see exactly which answers were not deterministic.

### A form that cannot be submitted

The system fills the form completely and then stops. A human reviews it and submits it themselves.

This is not enforced by a check that could be bypassed. There is simply no code that clicks a submit
button. The interface every part of the system uses to drive a form has no submit method to call.
Every one of the twelve test forms is checked at the end of its run to confirm the submit button was
never touched, and the live browser run additionally confirms the page never navigated away, since
a submitted form would have gone to a confirmation page.

### An artifact you can actually check

Each run produces a directory: a picture of the filled-in form, a record of every field and what
happened to it, the list of model-answered questions with confidences, and a frozen copy of the
application that produced it — so a later regeneration can never be mistaken for what was actually
filled.

If the run goes wrong it still produces all of this. A form that changed shape halts the run, and
the capture names the field it stopped on, with the partial fill intact and the completion figure
reporting how far it actually got rather than rounding a failure up to a finished form. Losing the
run is acceptable; losing the evidence of what went wrong is not.

## What the numbers say

| Platform | Forms tested | Filled | Filled without AI |
|---|---|---|---|
| Greenhouse | 4 | 100% | 70% |
| Lever | 4 | 100% | 75% |
| Ashby | 4 | 100% | 75% |

Every field that should hold a value holds one. Around three-quarters of them were placed by the
deterministic map with no AI involved at all, and the rest are the employer's own custom questions.

The second column is the one worth watching over time. If it starts falling while the first column
stays at 100%, it means a platform has changed its forms and the model is quietly covering for a map
that no longer fits — which costs money and replaces a reliable process with a guess. The full
figures are in the [Spike A gate record](../gates/spike-a.md).

## What this does not yet prove

The forms tested are faithful reconstructions of how these three platforms build their pages, not
copies of real job postings. They are accurate about the thing the field maps depend on, which is
what makes them a fair test of the mapping logic. But a reconstruction cannot surprise you, and real
pages do.

So one criterion is genuinely outstanding: one clean run against a real live posting on each
platform. Until those exist, the honest statement is that the approach works and has not yet met
reality. The gate record says so rather than reporting a pass.

Those runs need a person at a real employer's page rather than a test that can be run on demand, so
they happen in Phase 3, alongside the button in the review screen that a user would press to start
one. Doing them there means they go through exactly the path a real application takes.

## What was also built along the way

Phase 1 cannot run on nothing, so the parts of Phase 0 it depended on were built first: the project
scaffold and its lint rules, continuous integration, the two-tier AI client with recorded responses,
the tool registry that makes submission unreachable, the network wrapper that restricts which sites
can be contacted at all, and the twelve test forms.

The rest of Phase 0 was sample data — an email corpus, two example profiles, a set of past
application outcomes — and a database layer. Each of those is read by exactly one later phase and by
nothing before it, so rather than being held up front they now sit at the start of the phase that
uses them. Nothing was dropped; it moved to where it is first needed.

Two of those are worth calling out.

The test suite cannot reach the network. Not by convention — the socket layer is patched to refuse.
Every AI response is recorded once and replayed, which is what keeps the tests deterministic and
keeps development from exhausting a free-tier quota that allows 250 requests a day.

The tool registry makes the submission boundary structural. Every tool declares how consequential it
is, and tools marked as human-only have no binding an agent could reach. A test walks out from every
agent and proves none of them can get to one.
