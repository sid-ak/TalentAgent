"""Tests for evidence retrieval, requirement normalisation, and sufficiency scoring (Issue #23)."""

from pathlib import Path

import pytest
from talentagent.evidence.graph import (
    Accomplishment,
    AttestationClass,
)
from talentagent.evidence.retrieval import (
    DEFAULT_SUFFICIENCY_THRESHOLD,
    NormalizedRequirement,
    calculate_sufficiency,
    normalise_requirement,
    query_evidence,
)
from talentagent.evidence.store import LocalEvidenceStore

from tests.fixtures.evidence.seeding import seed_profile_a


@pytest.fixture
def store_a(tmp_path: Path) -> LocalEvidenceStore:
    """Return a store seeded with Profile A."""
    store = LocalEvidenceStore(tmp_path / "store_a")
    seed_profile_a(store)
    return store


def test_normalise_requirement_extracts_skills_and_years() -> None:
    """Requirement normalisation extracts canonical skills and experience requirements."""
    req = normalise_requirement("5+ years of experience with Python and Pub/Sub in production")
    assert req.min_years == 5
    assert "skill_python" in req.skills
    assert "skill_pubsub" in req.skills


def test_degenerate_case_zero_candidates_returns_zero_sufficiency() -> None:
    """A requirement with no matching candidates produces exactly 0.0 sufficiency score."""
    req = NormalizedRequirement(
        id="req_k8s",
        text="Kubernetes cluster management",
        skills=["skill_kubernetes"],
    )
    score = calculate_sufficiency(req, [])
    assert score == 0.0


def test_sufficiency_is_reproducible(store_a: LocalEvidenceStore) -> None:
    """Sufficiency calculation is a pure function: same input produces identical score."""
    req = normalise_requirement("Experience optimizing Python latency and Pub/Sub pipelines")
    res1 = query_evidence(req, store_a)
    res2 = query_evidence(req, store_a)

    assert res1.sufficiency == res2.sufficiency
    assert res1.sufficiency >= DEFAULT_SUFFICIENCY_THRESHOLD
    assert res1.meets_threshold is True
    assert len(res1.candidates) >= 1
    assert all(c.attestation_class == AttestationClass.VERIFIABLE for c in res1.candidates)


def test_derived_nodes_excluded_from_retrieval(store_a: LocalEvidenceStore) -> None:
    """Derived nodes in the store are never included in retrieval result candidates (G1)."""
    # Inject a derived candidate
    cand = Accomplishment(
        id="acc_model_py",
        claim="Unconfirmed Python claim",
        skills=["skill_python"],
        evidence=["art_1"],
        attestation_class=AttestationClass.DERIVED,
    )
    store_a.save_node(cand)

    req = normalise_requirement("Python microservices")
    res = query_evidence(req, store_a)

    assert not any(c.id == "acc_model_py" for c in res.candidates)
    assert not any(c.attestation_class == AttestationClass.DERIVED for c in res.candidates)
