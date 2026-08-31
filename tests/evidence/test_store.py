"""Tests for LocalEvidenceStore, query methods, and superseded handling (Spec §3.1, §3.4)."""

from pathlib import Path

import pytest
from talentagent.evidence.graph import (
    Accomplishment,
    Artifact,
    ArtifactSubtype,
    AttestationClass,
    Edge,
    EdgeType,
    EvidencePeriod,
    NodeType,
    Skill,
    Statement,
    StatementSource,
)
from talentagent.evidence.store import LocalEvidenceStore, NodeNotFound


@pytest.fixture
def store(tmp_path: Path) -> LocalEvidenceStore:
    """Return a clean LocalEvidenceStore backed by a temporary directory."""
    return LocalEvidenceStore(tmp_path / "evidence_store")


def test_save_and_retrieve_nodes(store: LocalEvidenceStore) -> None:
    """Nodes of all types can be saved and retrieved by ID."""
    art = Artifact(
        id="art_101",
        subtype=ArtifactSubtype.PR,
        title="PR #101: Add latency optimizations",
        url="https://github.com/example/repo/pull/101",
    )
    store.save_node(art)

    stmt = Statement(
        id="stm_201",
        statement=StatementSource(raw="Built the caching pipeline for user profiles."),
    )
    store.save_node(stmt)

    skill = Skill(id="skill_python", name="Python", category="Language")
    store.save_node(skill)

    acc = Accomplishment(
        id="acc_301",
        claim="Optimized latency by 40%",
        skills=["skill_python"],
        evidence=["art_101"],
        attestation_class=AttestationClass.VERIFIABLE,
    )
    store.save_node(acc)

    assert store.get_node("art_101") == art
    assert store.get_node("stm_201") == stmt
    assert store.get_node("skill_python") == skill
    assert store.get_node("acc_301") == acc

    with pytest.raises(NodeNotFound):
        store.get_node("nonexistent")


def test_supersedes_retires_from_active_but_retains_in_history(store: LocalEvidenceStore) -> None:
    """A SUPERSEDES edge retires the old claim from active() while keeping it in history()."""
    acc1 = Accomplishment(
        id="acc_v1",
        claim="Initial draft claim",
        skills=["skill_python"],
        evidence=["art_1"],
        attestation_class=AttestationClass.ATTESTED,
    )
    acc2 = Accomplishment(
        id="acc_v2",
        claim="Better substantiated claim",
        skills=["skill_python"],
        evidence=["art_1", "art_2"],
        attestation_class=AttestationClass.VERIFIABLE,
    )
    store.save_node(acc1)
    store.save_node(acc2)

    # Before superseding, both are active
    active_ids = {a.id for a in store.active()}
    assert active_ids == {"acc_v1", "acc_v2"}

    # acc_v2 supersedes acc_v1
    store.save_edge(
        Edge(
            source_id="acc_v2",
            source_type=NodeType.ACCOMPLISHMENT,
            target_id="acc_v1",
            target_type=NodeType.ACCOMPLISHMENT,
            edge_type=EdgeType.SUPERSEDES,
        )
    )

    # After superseding, acc_v1 is retired from active() but retained in history()
    assert {a.id for a in store.active()} == {"acc_v2"}
    assert {a.id for a in store.history()} == {"acc_v1", "acc_v2"}


def test_supporting_evidence_traversal(store: LocalEvidenceStore) -> None:
    """supporting_evidence() retrieves underlying Artifact and Statement nodes."""
    art = Artifact(id="art_1", subtype=ArtifactSubtype.COMMIT, title="Commit 1")
    stmt = Statement(id="stm_1", statement=StatementSource(raw="Statement 1"))
    store.save_node(art)
    store.save_node(stmt)

    acc = Accomplishment(
        id="acc_1",
        claim="Evidenced claim",
        evidence=["art_1", "stm_1"],
        attestation_class=AttestationClass.VERIFIABLE,
    )
    store.save_node(acc)

    evidence_nodes = store.supporting_evidence("acc_1")
    assert len(evidence_nodes) == 2
    assert art in evidence_nodes
    assert stmt in evidence_nodes


def test_queries_by_skill_period_and_class(store: LocalEvidenceStore) -> None:
    """Store query helpers filter active accomplishments appropriately."""
    acc1 = Accomplishment(
        id="acc_1",
        claim="Python backend",
        skills=["skill_python"],
        evidence=["art_1"],
        period=EvidencePeriod(start="2025-01", end="2025-06"),
        attestation_class=AttestationClass.VERIFIABLE,
    )
    acc2 = Accomplishment(
        id="acc_2",
        claim="Rust infra",
        skills=["skill_rust"],
        evidence=["art_2"],
        period=EvidencePeriod(start="2024-01", end="2024-12"),
        attestation_class=AttestationClass.ATTESTED,
    )
    store.save_node(acc1)
    store.save_node(acc2)

    assert [a.id for a in store.by_skill("skill_python")] == ["acc_1"]
    assert [a.id for a in store.by_skill("skill_rust")] == ["acc_2"]
    assert [a.id for a in store.by_class(AttestationClass.VERIFIABLE)] == ["acc_1"]
    assert [a.id for a in store.by_class(AttestationClass.ATTESTED)] == ["acc_2"]
    assert [a.id for a in store.by_period("2025-01")] == ["acc_1"]
