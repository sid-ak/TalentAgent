"""Tests for coverage metrics computation and credit trace-through (Spec §5.4, Issue #27)."""

from pathlib import Path

import pytest
from talentagent.composer.coverage import compute_coverage, trace_bullet_evidence
from talentagent.composer.package import ApplicationPackage, CreditedBullet, Identity
from talentagent.evidence.graph import (
    Artifact,
    AttestationClass,
    Statement,
)
from talentagent.evidence.store import LocalEvidenceStore

from tests.fixtures.evidence.seeding import seed_profile_a, seed_profile_b


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


def test_coverage_computation_profile_a_and_profile_b(
    store_a: LocalEvidenceStore, store_b: LocalEvidenceStore
) -> None:
    """Coverage computation calculates correct fractions for mixed and purely attested packages."""
    # Profile A package with 2 verifiable bullets
    pkg_a = ApplicationPackage(
        posting_id="job_a",
        identity=Identity(first_name="Ada", last_name="Lovelace", email="ada@example.com"),
        bullets=[
            CreditedBullet(
                text="Bullet 1",
                credits=["acc_7f21"],
                attestation_class=AttestationClass.VERIFIABLE,
            ),
            CreditedBullet(
                text="Bullet 2",
                credits=["acc_1c04"],
                attestation_class=AttestationClass.VERIFIABLE,
            ),
        ],
    )
    cov_a = compute_coverage(pkg_a, store_a)
    assert cov_a.total == 1.0
    assert cov_a.verifiable == 1.0
    assert cov_a.corroborated == 0.0
    assert cov_a.attested == 0.0

    # Profile B package with 2 attested bullets
    pkg_b = ApplicationPackage(
        posting_id="job_b",
        identity=Identity(first_name="Product", last_name="Lead", email="pm@example.com"),
        bullets=[
            CreditedBullet(
                text="Bullet 1",
                credits=["acc_2b88"],
                attestation_class=AttestationClass.ATTESTED,
            ),
            CreditedBullet(
                text="Bullet 2",
                credits=["acc_3c99"],
                attestation_class=AttestationClass.ATTESTED,
            ),
        ],
    )
    cov_b = compute_coverage(pkg_b, store_b)
    assert cov_b.total == 1.0
    assert cov_b.verifiable == 0.0
    assert cov_b.corroborated == 0.0
    assert cov_b.attested == 1.0


def test_credit_trace_through_resolves_to_artifacts_and_statements(
    store_a: LocalEvidenceStore, store_b: LocalEvidenceStore
) -> None:
    """Every credited bullet traces completely through to underlying artifacts or raw statements."""
    # Trace Profile A bullet to underlying PR and Doc artifacts
    bullet_a = CreditedBullet(
        text="Latency reduction",
        credits=["acc_7f21"],
        attestation_class=AttestationClass.VERIFIABLE,
    )
    prov_a = trace_bullet_evidence(bullet_a, store_a)
    assert len(prov_a) >= 2
    assert all(isinstance(p, Artifact) for p in prov_a)
    assert any("pr" in p.id for p in prov_a)

    # Trace Profile B bullet to underlying raw statement
    bullet_b = CreditedBullet(
        text="Onboarding redesign",
        credits=["acc_2b88"],
        attestation_class=AttestationClass.ATTESTED,
    )
    prov_b = trace_bullet_evidence(bullet_b, store_b)
    assert len(prov_b) == 1
    assert isinstance(prov_b[0], Statement)
    assert "onboarding" in prov_b[0].statement.raw
