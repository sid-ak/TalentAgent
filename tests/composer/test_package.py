"""Tests for application package schema, validation, and rejection rules (Spec §5.1, Issue #25)."""

from pathlib import Path

import pytest
from talentagent.composer.package import (
    ApplicationPackage,
    CreditedBullet,
    Identity,
    PackageValidationError,
    validate_package,
)
from talentagent.evidence.graph import Accomplishment, AttestationClass
from talentagent.evidence.store import LocalEvidenceStore

from tests.fixtures.evidence.seeding import seed_profile_a


@pytest.fixture
def store_a(tmp_path: Path) -> LocalEvidenceStore:
    """Return a store seeded with Profile A."""
    store = LocalEvidenceStore(tmp_path / "store_a")
    seed_profile_a(store)
    return store


def test_package_schema_spec_5_1_roundtrip() -> None:
    """Spec §5.1 package schema serializes and validates accurately."""
    pkg = ApplicationPackage(
        posting_id="job_9a2",
        identity=Identity(first_name="Ada", last_name="Lovelace", email="ada@example.com"),
        bullets=[
            CreditedBullet(
                text="Reduced p99 ingest latency 62% by tiering model routing",
                credits=["acc_7f21"],
                attestation_class=AttestationClass.VERIFIABLE,
                artifacts=["art_pr_412", "art_pr_419"],
                requirement_ids=["req_3"],
            )
        ],
    )
    assert len(pkg.bullets) == 1
    assert pkg.bullets[0].credits == ["acc_7f21"]
    assert pkg.bullets[0].attestation_class == AttestationClass.VERIFIABLE

    # Dotted path resolution for field maps
    assert pkg.resolve_path("identity.first_name") == "Ada"
    assert pkg.resolve_path("identity.full_name") == "Ada Lovelace"
    with pytest.raises(KeyError):
        pkg.resolve_path("identity.nonexistent_field")


def test_package_validation_rejects_nonexistent_credit(store_a: LocalEvidenceStore) -> None:
    """A package crediting a nonexistent node fails validation."""
    pkg = ApplicationPackage(
        posting_id="job_1",
        identity=Identity(first_name="Ada", last_name="Lovelace", email="ada@example.com"),
        bullets=[
            CreditedBullet(
                text="Ghost claim",
                credits=["acc_nonexistent"],
                attestation_class=AttestationClass.VERIFIABLE,
            )
        ],
    )
    with pytest.raises(PackageValidationError, match="non-existent node"):
        validate_package(pkg, store_a)


def test_package_validation_rejects_derived_credit(store_a: LocalEvidenceStore) -> None:
    """A package crediting a DERIVED accomplishment fails validation (Guardrail G1)."""
    derived_acc = Accomplishment(
        id="acc_derived_test",
        claim="Derived claim",
        skills=["skill_python"],
        evidence=["art_pr_412"],
        attestation_class=AttestationClass.DERIVED,
    )
    store_a.save_node(derived_acc)

    pkg = ApplicationPackage(
        posting_id="job_1",
        identity=Identity(first_name="Ada", last_name="Lovelace", email="ada@example.com"),
        bullets=[
            CreditedBullet(
                text="Derived claim bullet",
                credits=["acc_derived_test"],
                attestation_class=AttestationClass.DERIVED,
            )
        ],
    )
    with pytest.raises(PackageValidationError, match="DERIVED"):
        validate_package(pkg, store_a)
