"""Tests for evidence graph models, edge legality, and invariants (Spec §3.1, §3.3, §3.4)."""

import json
from typing import Any

import pytest
from pydantic import ValidationError
from talentagent.evidence.graph import (
    Accomplishment,
    AttestationClass,
    Edge,
    EdgeType,
    NodeType,
    Statement,
    StatementSource,
)


def test_spec_3_3_artifact_backed_accomplishment_roundtrip() -> None:
    """Spec §3.3 artifact-backed accomplishment JSON document round-trips without loss."""
    raw_doc: dict[str, Any] = {
        "id": "acc_7f21",
        "claim": "Cut p99 ingest latency by tiering the classifier",
        "skills": ["skill_pubsub", "skill_python", "skill_model_routing"],
        "metrics": [
            {
                "name": "p99_latency",
                "delta": -0.62,
                "unit": "ratio",
                "basis": "prod dashboard, 30d",
            }
        ],
        "evidence": ["art_pr_412", "art_pr_419", "art_doc_designreview"],
        "class": "verifiable",
        "period": {"start": "2025-03", "end": "2025-06"},
        "confidence": 0.91,
        "derived_by": "evidence@2026-08-14T03:12Z",
    }
    acc = Accomplishment.model_validate(raw_doc)
    assert acc.id == "acc_7f21"
    assert acc.attestation_class == AttestationClass.VERIFIABLE
    assert len(acc.evidence) == 3
    assert acc.metrics[0].delta == -0.62

    # Serialize back and compare dicts
    dumped = json.loads(acc.model_dump_json(by_alias=True, exclude_none=True))
    assert dumped == raw_doc


def test_spec_3_3_statement_backed_accomplishment_roundtrip() -> None:
    """Spec §3.3 statement-backed accomplishment JSON document round-trips without loss."""
    raw_doc: dict[str, Any] = {
        "id": "acc_2b88",
        "claim": "Led the migration of 40 services to a new auth provider",
        "skills": ["skill_auth", "skill_migration", "skill_leadership"],
        "metrics": [
            {
                "name": "services_migrated",
                "value": 40,
                "unit": "count",
                "basis": "user-stated",
            }
        ],
        "evidence": ["stm_0091"],
        "class": "attested",
        "statement": {
            "raw": (
                "i ran the auth migration last year, about 40 services, "
                "took two quarters, i was driving it not just contributing"
            ),
            "elicited_by": "gap:req_5 on job_9a2",
            "asserted_at": "2026-08-14",
            "artifact_producible": False,
        },
    }
    acc = Accomplishment.model_validate(raw_doc)
    assert acc.id == "acc_2b88"
    assert acc.attestation_class == AttestationClass.ATTESTED
    assert acc.statement is not None
    assert acc.statement.raw == raw_doc["statement"]["raw"]

    dumped = json.loads(acc.model_dump_json(by_alias=True, exclude_none=True))
    assert dumped == raw_doc


def test_invariant_1_non_empty_provenance() -> None:
    """An Accomplishment with empty evidence raises a validation error (Invariant 1)."""
    with pytest.raises(ValidationError):
        Accomplishment(
            id="acc_bad",
            claim="Empty evidence claim",
            evidence=[],
            attestation_class=AttestationClass.VERIFIABLE,
        )


def test_invariant_3_verbatim_statement_retention() -> None:
    """Statement raw text is retained verbatim including whitespace and non-ASCII (Invariant 3)."""
    tricky_raw = (
        '  Leading whitespace, newlines:\n\tSpecial symbols: © "quoted" & emoji 🚀\n'
        "Trailing spaces   "
    )
    stmt = Statement(
        id="stm_01",
        statement=StatementSource(raw=tricky_raw),
    )
    assert stmt.statement.raw == tricky_raw
    dumped = json.loads(stmt.model_dump_json())
    restored = Statement.model_validate(dumped)
    assert restored.statement.raw == tricky_raw
    assert restored.statement.raw == stmt.statement.raw


def test_edge_connectivity_legality() -> None:
    """Edge creation validates source and target node types per Spec §3.1."""
    # Legal edges
    e1 = Edge(
        source_id="art_1",
        source_type=NodeType.ARTIFACT,
        target_id="acc_1",
        target_type=NodeType.ACCOMPLISHMENT,
        edge_type=EdgeType.EVIDENCES,
    )
    assert e1.edge_type == EdgeType.EVIDENCES

    e2 = Edge(
        source_id="acc_1",
        source_type=NodeType.ACCOMPLISHMENT,
        target_id="skill_1",
        target_type=NodeType.SKILL,
        edge_type=EdgeType.DEMONSTRATES,
    )
    assert e2.edge_type == EdgeType.DEMONSTRATES

    e3 = Edge(
        source_id="metric_1",
        source_type=NodeType.METRIC,
        target_id="acc_1",
        target_type=NodeType.ACCOMPLISHMENT,
        edge_type=EdgeType.QUANTIFIES,
    )
    assert e3.edge_type == EdgeType.QUANTIFIES

    e4 = Edge(
        source_id="acc_2",
        source_type=NodeType.ACCOMPLISHMENT,
        target_id="acc_1",
        target_type=NodeType.ACCOMPLISHMENT,
        edge_type=EdgeType.SUPERSEDES,
    )
    assert e4.edge_type == EdgeType.SUPERSEDES

    # Illegal edges
    with pytest.raises(ValidationError):
        Edge(
            source_id="skill_1",
            source_type=NodeType.SKILL,
            target_id="acc_1",
            target_type=NodeType.ACCOMPLISHMENT,
            edge_type=EdgeType.DEMONSTRATES,
        )

    with pytest.raises(ValidationError):
        Edge(
            source_id="acc_1",
            source_type=NodeType.ACCOMPLISHMENT,
            target_id="art_1",
            target_type=NodeType.ARTIFACT,
            edge_type=EdgeType.EVIDENCES,
        )


def test_attestation_class_properties() -> None:
    """Attestation class enum properties reflect Appendix A."""
    assert AttestationClass.VERIFIABLE.admissible is True
    assert AttestationClass.VERIFIABLE.inspectable is True
    assert AttestationClass.VERIFIABLE.artifact_exists is True

    assert AttestationClass.CORROBORATED.admissible is True
    assert AttestationClass.CORROBORATED.inspectable is False
    assert AttestationClass.CORROBORATED.artifact_exists is True

    assert AttestationClass.ATTESTED.admissible is True
    assert AttestationClass.ATTESTED.inspectable is False
    assert AttestationClass.ATTESTED.artifact_exists is False

    assert AttestationClass.DERIVED.admissible is False
    assert AttestationClass.DERIVED.inspectable is False
    assert AttestationClass.DERIVED.artifact_exists is False
