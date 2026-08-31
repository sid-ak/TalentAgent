"""Gaps and elicitation: FLAG, ELICIT, and statement promotion (Spec §5.3, §3.5, Issue #26).

`gaps[]` is a deliverable reporting what the system refuses to claim. Elicitation emits exactly
one scoped question per missing requirement requesting specifics (quantity, timeframe, role).
Promotion persists user-originated statements verbatim and produces `attested` accomplishments.
"""

from __future__ import annotations

import datetime

from pydantic import BaseModel, ConfigDict

from talentagent.composer.package import Gap
from talentagent.evidence.graph import (
    Accomplishment,
    AttestationClass,
    Edge,
    EdgeType,
    EvidencePeriod,
    Metric,
    NodeType,
    Statement,
    StatementSource,
)
from talentagent.evidence.store import EvidenceStore


class Question(BaseModel):
    """A single scoped elicitation question (Spec §3.5).

    Type-level guarantee: elicit_evidence returns a single Question object, ensuring a questionnaire
    is unproducible by construction.
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    requirement_id: str
    text: str
    context: str | None = None


def build_gap_question(gap: Gap) -> Question:
    """Build a question requesting quantity, timeframe, and role relative to team."""
    question_text = (
        f"Nothing in the evidence graph touches {gap.text!r}. Have you worked on this, "
        "over what timeframe, what was your specific role vs the team's, and what quantitative "
        "outcome or scale resulted?"
    )
    return Question(
        id=f"q_{gap.requirement_id}",
        requirement_id=gap.requirement_id,
        text=question_text,
        context=gap.text,
    )


def elicit_evidence(gap: Gap) -> Question:
    """Emit exactly one scoped question for a missing requirement (Side-effect: write-draft).

    Cannot author a Statement or mutate the graph.
    """
    return build_gap_question(gap)


def promote_statement(
    answer: str,
    store: EvidenceStore,
    gap: Gap | None = None,
    claim: str | None = None,
    skills: list[str] | None = None,
    metrics: list[Metric] | None = None,
    period: EvidencePeriod | None = None,
    artifact_producible: bool = False,
) -> tuple[Statement, Accomplishment]:
    """Promote a raw statement to an attested Accomplishment (write-user-originated).

    Stores the raw text byte-identical to what the user typed (Invariant 3).
    """
    raw_text = answer
    now_date = datetime.datetime.now(datetime.UTC).date().isoformat()

    stm_id = f"stm_{abs(hash(raw_text)) % 1000000:06d}"
    elicited_by = f"gap:{gap.requirement_id}" if gap else None

    stmt_source = StatementSource(
        raw=raw_text,
        elicited_by=elicited_by,
        asserted_at=now_date,
        artifact_producible=artifact_producible,
    )
    stmt = Statement(
        id=stm_id,
        statement=stmt_source,
        period=period,
    )
    store.save_node(stmt)

    acc_id = f"acc_{abs(hash(raw_text)) % 1000000:06d}"
    canonical_claim = claim or raw_text.strip().split("\n")[0][:120]

    acc = Accomplishment(
        id=acc_id,
        claim=canonical_claim,
        skills=skills or [],
        metrics=metrics or [],
        evidence=[stm_id],
        statement=stmt_source,
        period=period,
        attestation_class=AttestationClass.ATTESTED,
    )
    store.save_node(acc)

    store.save_edge(
        Edge(
            source_id=stm_id,
            source_type=NodeType.STATEMENT,
            target_id=acc_id,
            target_type=NodeType.ACCOMPLISHMENT,
            edge_type=EdgeType.EVIDENCES,
        )
    )

    if skills:
        for sk in skills:
            store.save_edge(
                Edge(
                    source_id=acc_id,
                    source_type=NodeType.ACCOMPLISHMENT,
                    target_id=sk,
                    target_type=NodeType.SKILL,
                    edge_type=EdgeType.DEMONSTRATES,
                )
            )

    return stmt, acc
