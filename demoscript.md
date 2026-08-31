# TalentAgent — 4 minute demo script

Judging weights: Innovation & Operational Utility 40%, Architectural Discipline 30%, Demo &
Production Readiness 30%. The third one explicitly wants "a live, unedited demo, a clean
architecture diagram, reproducible setup, and visible proof it runs on Google Cloud."

So: record in one take, no cuts. Keep the browser address bar visible the entire time — the
`.run.app` URL is doing quiet work in every frame.

## Before you hit record

1. Open https://talentagent-482181354691.us-central1.run.app in a clean window. Session is already
   reset, so it should say "nothing added yet".
2. Open a second tab on the Cloud Run console for the `talentagent` service. Do not show it yet.
3. Have this file open on a second monitor or phone.
4. Zoom the browser to about 110% so text is readable in the recording.

The two blocks of text you will paste are at the bottom. Have them on your clipboard manager, or
just type from the script.

---

## 0:00 – 0:25 — The hook

Do: sit on the app, nothing typed yet.

Say, roughly:

> Every tool that writes job applications does the same thing: it hands your resume and a job
> posting to a model and asks for sentences. Some of those sentences are true. You cannot tell
> which — and neither can the model, because nothing in that setup separates a fact you gave it
> from one it invented to fill a gap.
>
> TalentAgent inverts that. The model never decides *whether* a line can be written. It only
> decides how to phrase one that's already been earned.

Do not explain the architecture yet. Show it first.

## 0:25 – 1:00 — Give it something true

Do: paste EVIDENCE 1 into the left box, click Add this. Then EVIDENCE 2, Add this.

Say:

> This is the only material it's allowed to work from. Two things I've actually done, in my own
> words — not a resume, not a form.

## 1:00 – 1:55 — Run it, and watch it refuse

Do: paste the JOB POSTING into the middle box. Click Run the agent.

It takes eight to ten seconds. Do not go silent — talk over it:

> It's calling Gemini twice. Flash-Lite reads the posting and separates the real requirements from
> the perks and the boilerplate. Then, for each requirement, it searches what I've written and
> scores how well it's covered — and that score is computed outside the model. It's arithmetic.

When the trace fills in, point at the four "looked for" steps:

> Kubernetes — 63% match, over the threshold, it can write that one. Go — over. The auth
> migration — over.
>
> And then Rust. Zero percent. Nothing I wrote touches it.

Point at the right column:

> Three lines it can back up. And instead of a fourth line about Rust, it asks me a question.
> **That refusal is the entire product.** Every other tool would have written me a confident
> sentence about a Rust data pipeline I have never touched.

That is your 40% moment. Do not rush it.

## 1:55 – 2:30 — Close the loop

Do: scroll to the question, type the ANSWER into its box, click Add answer and re-run.

Say while it runs:

> My answer goes in verbatim — byte for byte, not a paraphrase. Now it re-runs with evidence it
> didn't have.

When the fourth line appears:

> There's the fourth line. It exists now because I told it something true, not because it guessed.
> The system gets better at describing me by asking. That's the loop.

## 2:30 – 2:55 — It fills the form and stops

Do: scroll down in the right column, click Greenhouse.

Say:

> Same package, straight onto a real Greenhouse form. That's a measured completion rate, not a
> hardcoded one — it re-enumerates the form because fields can be revealed by earlier answers.
>
> And it cannot submit. Not "we told it not to" — the page interface it drives has no submit
> method on it at all. There's no code path to disable, because there's no code path.

## 2:55 – 3:25 — After you apply

Do: paste the REPLIES into the box in section 4. Click Read the replies.

Say:

> Applying isn't the end — tracking where everything stands is the part that actually rots.
> Paste the replies in and Gemini labels each one. But it doesn't decide what happens next: a
> transition table from the spec does that.
>
> Acknowledged, then a recruiter, then a rejection. And the LinkedIn spam in the middle moved
> nothing, because the table has no transition for it. The model proposes, the table disposes —
> so it can't invent a state that doesn't exist.

## 3:25 – 3:50 — Proof it's on Google Cloud

Do: point at the address bar, then switch to the Cloud Run console tab. Show the service, the
region, the revision, and the request log.

Say:

> Everything you just watched ran on Cloud Run — this is the live service, deployed from the
> Dockerfile in the repo. Gemini 3.5 Flash-Lite and 3.6 Flash through the GenAI SDK. The README
> has the deploy as a single command.

Hold the console on screen for a solid five seconds. This is the "visible proof" the rubric asks
for by name.

## 3:50 – 4:00 — Land it

Say:

> Two hundred and eighty tests, no network calls in any of them. The guardrails are mechanisms,
> not prompt instructions — and where one isn't built yet, the status endpoint says so instead of
> claiming otherwise.
>
> It writes applications it can prove. And when it can't prove one, it asks.

Stop recording.

---

## If something goes wrong

- Agent run hangs past 20 seconds: it is a cold start on a scaled-to-zero container. Keep talking,
  it will come back. Do not refresh.
- Gemini returns an error: say "that's the free tier rate limiting" and re-run. It is honest and
  it recovers.
- Do not reset the session mid-recording; you lose your evidence and have to retype it.

---

## The text to paste

### EVIDENCE 1

```
Cut Kubernetes rollout time from 40 minutes to 6 by rewriting the deploy pipeline in Go, across 30 services.
```

### EVIDENCE 2

```
Led the Python migration of our authentication service off a legacy monolith, coordinating four teams over two quarters.
```

### JOB POSTING

```
Senior Platform Engineer

What you will do:
- Own our Kubernetes deployment tooling and reduce time-to-production
- Write Go services that operate at scale
- Lead a migration of authentication infrastructure
- Run our Rust-based data ingestion layer

Perks: free lunch, dog-friendly office, unlimited PTO.
```

### ANSWER to the Rust question

```
I rewrote our ingestion workers in Rust over about five months, taking them from 12,000 to 90,000 events per second on the same hardware. I owned the Rust side; two other engineers handled the Kafka topics.
```

### REPLIES

```
From: careers@stripe.com
Thanks for applying to the Senior Platform Engineer role. Our team will review it.
---
From: hana@stripe.com
I'd love to set up a 30 minute intro call about the role. Are you free Thursday?
---
From: noreply@linkedin.com
12 new jobs for you this week.
---
From: careers@stripe.com
After careful consideration we've decided to move forward with other candidates.
```

---

## Devpost text, if you want it pre-written

Category: The Collaborative Partner.

> TalentAgent writes job applications it can prove. For each requirement in a posting it searches
> what you've actually done, scores the coverage outside the model, and either writes a line backed
> by that evidence or asks you a question — it has no path that lets it invent the difference. It
> fills the employer's form and stops, because pressing submit is yours.
>
> Built on Gemini 3.5 Flash-Lite and 3.6 Flash through the GenAI SDK, deployed on Cloud Run. The
> interesting output of a run isn't the bullets — it's the questions.
