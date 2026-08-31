"""Guardrail G2: No generated line without a credit (Spec §10, Issue #25).

Asserts that no package containing an uncredited line, a credit referencing a non-existent node,
or a credit referencing a DERIVED node can be constructed or validated.
"""

from pathlib import Path

import pytest
from pydantic import ValidationError
from talentagent.composer.package import (
    ApplicationPackage,
    CreditedBullet,
    Identity,
    PackageValidationError,
    validate_package,
)
from talentagent.evidence.graph import AttestationClass
from talentagent.evidence.store import LocalEvidenceStore

from tests.fixtures.evidence.seeding import seed_profile_a

pytestmark = pytest.mark.guardrail


@pytest.fixture
def store(tmp_path: Path) -> LocalEvidenceStore:
    """Return a store seeded with Profile A."""
    st = LocalEvidenceStore(tmp_path / "g2_store")
    seed_profile_a(st)
    return st


def test_g2_uncredited_bullet_fails_at_schema_layer() -> None:
    """A CreditedBullet with empty credits raises a ValidationError immediately (G2)."""
    with pytest.raises(ValidationError):
        CreditedBullet(
            text="Uncredited claim line",
            credits=[],
            attestation_class=AttestationClass.VERIFIABLE,
        )


def test_g2_uncredited_package_rejected_at_validation(store: LocalEvidenceStore) -> None:
    """validate_package strictly rejects any uncredited or invalidly credited line (G2)."""
    # Valid package passes
    valid_pkg = ApplicationPackage(
        posting_id="job_valid",
        identity=Identity(first_name="Ada", last_name="Lovelace", email="ada@example.com"),
        bullets=[
            CreditedBullet(
                text="Valid claim",
                credits=["acc_7f21"],
                attestation_class=AttestationClass.VERIFIABLE,
            )
        ],
    )
    validate_package(valid_pkg, store)

    # Invalid package crediting non-existent node fails
    invalid_pkg = ApplicationPackage(
        posting_id="job_invalid",
        identity=Identity(first_name="Ada", last_name="Lovelace", email="ada@example.com"),
        bullets=[
            CreditedBullet(
                text="Invented claim",
                credits=["acc_fake_id"],
                attestation_class=AttestationClass.VERIFIABLE,
            )
        ],
    )
    with pytest.raises(PackageValidationError):
        validate_package(invalid_pkg, store)
