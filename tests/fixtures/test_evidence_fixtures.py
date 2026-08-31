"""Tests asserting evidence fixture properties and Profile B purity (Issue #10, ADR-0002)."""

from pathlib import Path

import pytest
from talentagent.evidence.graph import Artifact, AttestationClass
from talentagent.evidence.store import LocalEvidenceStore

from tests.fixtures.evidence.seeding import (
    seed_profile_a,
    seed_profile_b,
)


@pytest.fixture
def store_a(tmp_path: Path) -> LocalEvidenceStore:
    """Return a store seeded with Profile A."""
    store = LocalEvidenceStore(tmp_path / "store_a")
    seed_profile_a(store)
    return store


@pytest.fixture
def store_b(tmp_path: Path) -> LocalEvidenceStore:
    """Return a store seeded with Profile B."""
    store = LocalEvidenceStore(tmp_path / "store_b")
    seed_profile_b(store)
    return store


def test_profile_a_contains_verifiable_artifacts(store_a: LocalEvidenceStore) -> None:
    """Profile A contains verifiable accomplishments and underlying artifacts."""
    active = store_a.active()
    assert len(active) >= 2
    assert any(acc.attestation_class == AttestationClass.VERIFIABLE for acc in active)

    # Verify supporting artifacts exist
    acc_7f21_evidence = store_a.supporting_evidence("acc_7f21")
    assert len(acc_7f21_evidence) >= 2
    assert all(isinstance(n, Artifact) for n in acc_7f21_evidence)


def test_profile_b_contains_zero_public_artifacts(store_b: LocalEvidenceStore) -> None:
    """Profile B contains ZERO verifiable and ZERO corroborated nodes; all claims are attested.

    This proves that Spike B measures what it claims to: the graded provenance design functions
    for non-engineering candidates whose evidence consists solely of elicited statements (ADR-0002).
    """
    active = store_b.active()
    assert len(active) >= 2

    # Assert 100% of accomplishments are attested
    for acc in active:
        assert acc.attestation_class == AttestationClass.ATTESTED, (
            f"Profile B accomplishment {acc.id} has class {acc.attestation_class.value}; "
            f"must be attested"
        )

    # Assert zero verifiable and zero corroborated accomplishments in active or history
    assert len(store_b.by_class(AttestationClass.VERIFIABLE)) == 0
    assert len(store_b.by_class(AttestationClass.CORROBORATED)) == 0
