"""Tests for gaps, elicitation, and statement promotion (Spec §5.3, §3.5, Issue #26)."""

from pathlib import Path

from talentagent.composer.package import Gap, GapAction
from talentagent.evidence.elicitation import (
    Question,
    elicit_evidence,
    promote_statement,
)
from talentagent.evidence.graph import AttestationClass
from talentagent.evidence.store import LocalEvidenceStore


def test_elicit_evidence_returns_single_scoped_question() -> None:
    """elicit_evidence returns exactly one Question requesting specifics (Spec §3.5)."""
    gap = Gap(
        requirement_id="req_k8s",
        text="Kubernetes production deployments",
        sufficiency=0.0,
        action=GapAction.ELICIT,
    )
    q = elicit_evidence(gap)
    assert isinstance(q, Question)
    assert q.requirement_id == "req_k8s"
    assert "role" in q.text.lower()
    assert "timeframe" in q.text.lower()


def test_promote_statement_stores_verbatim_raw_text_and_attested_class(tmp_path: Path) -> None:
    """promote_statement preserves raw statement verbatim and marks attested (Invariant 3)."""
    store = LocalEvidenceStore(tmp_path / "store")
    raw_user_text = "  i migrated 12 kubernetes clusters across 3 regions in 2024  "

    gap = Gap(
        requirement_id="req_k8s",
        text="Kubernetes cluster migration",
        sufficiency=0.0,
        action=GapAction.ELICIT,
    )

    stmt, acc = promote_statement(
        answer=raw_user_text,
        store=store,
        gap=gap,
        skills=["skill_kubernetes"],
    )

    # Asserts Invariant 3: exact verbatim preservation
    assert stmt.statement.raw == raw_user_text
    assert acc.statement is not None
    assert acc.statement.raw == raw_user_text
    assert acc.attestation_class == AttestationClass.ATTESTED
    assert acc.evidence == [stmt.id]

    # Verify nodes in store
    retrieved_acc = store.get_node(acc.id)
    assert retrieved_acc.id == acc.id

    # Verify supporting evidence via edge
    ev = store.supporting_evidence(acc.id)
    assert len(ev) == 1
    assert ev[0].id == stmt.id
