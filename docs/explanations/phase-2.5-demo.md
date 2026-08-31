# Phase 2.5: Interactive demo and review surface

## What this phase was for

A core principle of TalentAgent is that the human retains final authority over all irreversible
actions (`G3`, `ADR-0001`). Agents can retrieve evidence, verify sufficiency, compose credited
packages, and mechanically fill ATS forms — but they never submit an application or invent a claim
out of thin air (`G1`, `G2`).

To make this contract tangible and demonstrable, Phase 2.5 introduces an interactive Angular web
application. It serves as both the human review surface and the hackathon demonstration interface,
bringing together the deterministic foundation of Phase 1 and the evidence-constrained composition
engine of Phase 2.

## What now exists

### 1. Candidate profile management

The review interface allows candidates to provide and manage their ground-truth experience through
multiple modalities:
- Resume upload: PDF documents are parsed in the backend using `pypdf`, extracting skills, metrics,
  and work history into structured candidate nodes.
- GitHub ingestion: syncs public commits, pull requests, and documentation into inspectable artifact
  nodes with deterministic classification.
- LinkedIn references: stores external profile links and portfolio materials.
- Verbatim statements: candidates write raw accomplishment claims directly in their own words,
  guaranteeing byte-for-byte retention with no model rephrasing (`Spec §3.4 Invariant 3`).
- Profile switching: seamless toggling between preset Profile A (engineering artifacts), Profile B
  (non-engineering attested statements only), and custom candidate profiles.

### 2. Interactive evidence graph explorer

The evidence graph is rendered as an interactive network visualizer:
- Nodes: Color-coded representation of Artifacts, Statements, Skills, Metrics, and Accomplishments.
- Attestation badges: immediate visibility into `verifiable`, `corroborated`, `attested`, and
  `derived` claims.
- The derived quarantine boundary: a visual boundary illustrating how unconfirmed model inferences
  (`derived` nodes) are strictly quarantined from application composer queries (`G1`).
- Node inspector: detailed metadata inspection showing direct evidence edges, source links, and
  mutation timelines.

### 3. Two-pass apply and review workflow

The central feature of the review surface is the interactive execution of the two-pass apply flow:

#### Pass 1: Credited composition and sufficiency
- Requirement extraction: parses job posting descriptions into discrete requirement items.
- Deterministic sufficiency scoring: visual meters display calculated sufficiency against the
  candidate graph (threshold 0.60), computed outside any language model (`ADR-0008`).
- Credited bullet inspection: every generated resume bullet displays an attestation class badge.
  Clicking any bullet opens an evidence drawer tracing the claim directly to underlying PRs,
  commits, or candidate statements.
- Adversarial posting verification: users can select adversarial, out-of-scope requirements (e.g.
  quantum computing, blockchain smart contracts) and watch the system route 100% of them to gaps
  with zero uncredited hallucinations.

#### Live elicitation and statement promotion
- Missing evidence generates an explicit gap deliverable (`FLAG` vs `ELICIT`).
- For `ELICIT` gaps, the interface presents a single scoped question requesting specifics (timeframe,
  scale, and specific role).
- Candidates can type their answer live in the UI. Submitting the answer triggers promotion directly
  into an `attested` Statement node and immediately re-composes the application package with 100%
  provenance credit (`G2`).

#### Pass 2: ATS form fill execution
- Supported platforms: Greenhouse, Lever, and Ashby.
- Step-by-step form fill playback: animated visual inspection of mapped form fields (`identity`,
  `links`, `materials`, `screening_answers`).
- Fallback question resolution: logs model fallback decisions for custom employer questions.
- Halt-and-capture preview: displays captured screenshot previews of filled forms.
- Human review gate: the `Submit Application` action is disabled for automated agents and enforces
  human authorization before final submission (`G3`).

### 4. Guardrails and zero-budget monitor

The dashboard provides real-time system monitoring:
- Live status indicators for Invariants G1 through G7.
- Gemini Flash and Flash-Lite daily quota tracker under the zero-budget constraint (`ADR-0012`).

## Architecture and deployment

The frontend is an Angular single-page application located in `frontend/` that compiles into static
assets in `web/`. The static bundle is served locally via a zero-dependency Python API server
(`talentagent/ui/server.py` and `scripts/serve_demo.py`) and is pre-configured for static deployment
on Firebase Hosting (`firebase.json`).
