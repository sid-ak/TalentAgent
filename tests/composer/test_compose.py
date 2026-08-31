"""Tests for constrained composition Pass 1 (Spec §5.5, Issue #24)."""

from pathlib import Path

import pytest
from talentagent.composer.compose import compose_package
from talentagent.composer.package import GapAction, Identity
from talentagent.evidence.graph import AttestationClass
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


def test_compose_package_profile_a(store_a: LocalEvidenceStore) -> None:
    """Compose produces credited bullets for matching requirements and gaps for missing ones."""
    identity = Identity(first_name="Test", last_name="Engineer", email="eng@example.com")
    requirements = [
        "Python backend optimization with Pub/Sub pipelines",
        "5+ years Kubernetes and Terraform cloud infrastructure",
    ]

    pkg = compose_package(
        posting_id="job_backend",
        requirements=requirements,
        identity=identity,
        store=store_a,
    )

    # 1 supported requirement -> 1 credited bullet
    assert len(pkg.bullets) == 1
    assert pkg.bullets[0].credits == ["acc_7f21"]
    assert pkg.bullets[0].attestation_class == AttestationClass.VERIFIABLE

    # 1 unsupported requirement -> 1 gap with ELICIT action
    assert len(pkg.gaps) == 1
    assert pkg.gaps[0].action == GapAction.ELICIT
    assert pkg.gaps[0].sufficiency == 0.0
    assert pkg.gaps[0].question is not None


def test_compose_package_profile_b(store_b: LocalEvidenceStore) -> None:
    """Non-engineering profile produces a package with 100% attested coverage."""
    identity = Identity(first_name="Product", last_name="Lead", email="pm@example.com")
    requirements = [
        "Product strategy and customer onboarding optimization",
        "Cross-functional stakeholder management",
    ]

    pkg = compose_package(
        posting_id="job_pm",
        requirements=requirements,
        identity=identity,
        store=store_b,
    )

    assert len(pkg.bullets) == 2
    for b in pkg.bullets:
        assert b.attestation_class == AttestationClass.ATTESTED

    assert pkg.coverage is not None
    assert pkg.coverage.attested == 1.0
    assert pkg.coverage.verifiable == 0.0
