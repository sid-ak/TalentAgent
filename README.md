# TalentAgent

TalentAgent is the agent your career never had: it works while you sleep, backs every resume claim
with real work, and learns which employers actually hire people like you.

An event-driven multi-agent system that operates a job search as a long-running workflow. Five
specialist agents maintain an evidence graph of what the user has actually accomplished, derive
application pipeline state from the user's inbox, compose applications in which every generated
claim traces to user-originated evidence, and run a closed experiment loop over outcomes.

The system acts autonomously on preparation, tracking, and analysis. Irreversible and
identity-asserting actions — account creation, authentication, submission, accepting an offer —
remain human-only.

Documentation site: https://sid-ak.github.io/TalentAgent/

## Documentation

| Document | Answers |
|---|---|
| [Why](docs/TalentAgent-Why.md) | Why the product exists and what the category gets wrong |
| [Specification](docs/TalentAgent-Spec.md) | Agent contracts, schemas, coordination, guardrails, scope |
| [Architecture](docs/TalentAgent-Architecture.md) | Where things run, what they may reach, how work propagates |
| [Plan](docs/TalentAgent-Plan.md) | The six phases, ordered by risk retired |
| [Decision records](docs/ADRs/README.md) | Why each load-bearing decision was taken, and what it cost |
| [AGENTS.md](AGENTS.md) | Working agreement for contributors, human and agent |

## Status

Specification, architecture, and decision records are complete. Implementation is tracked in
[issues](https://github.com/sid-ak/TalentAgent/issues), grouped into six
[milestones](https://github.com/sid-ak/TalentAgent/milestones) that mirror the phases in the plan.

## Building the documentation locally

The toolchain is pinned in `requirements-docs.txt` and kept separate from the project's own
dependencies, so nothing needs installing into the project environment:

1. `uvx --with-requirements requirements-docs.txt --from mkdocs mkdocs serve`: live-reloading
   preview on `http://127.0.0.1:8000/TalentAgent/`.
2. `uvx --with-requirements requirements-docs.txt --from mkdocs mkdocs build --strict`: what CI
   runs; fails on broken internal links.

The site includes a code reference generated from the source on every build, so a new module
documents itself. `mkdocs serve` watches `talentagent/` as well as `docs/`.
