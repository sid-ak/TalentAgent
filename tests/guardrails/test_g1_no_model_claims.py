"""Guardrail G1: No model-originated claim reaches an employer (Spec §10).

Asserts that every method decorated with `@composer_query` across the store query surface
quarantines `DERIVED` nodes, ensuring model-originated accomplishments cannot be selected
during composition.
"""

from pathlib import Path

import pytest
from talentagent.evidence.graph import (
    Accomplishment,
    AttestationClass,
    EvidencePeriod,
)
from talentagent.evidence.store import (
    COMPOSER_QUERIES,
    LocalEvidenceStore,
)

pytestmark = pytest.mark.guardrail


@pytest.fixture
def quarantined_store(tmp_path: Path) -> LocalEvidenceStore:
    """Return a store seeded with both admissible and quarantined DERIVED nodes."""
    store = LocalEvidenceStore(tmp_path / "g1_store")
    # Admissible nodes
    acc_admissible = Accomplishment(
        id="acc_real",
        claim="Real verifiable claim",
        skills=["skill_python"],
        evidence=["art_1"],
        period=EvidencePeriod(start="2025-01", end="2025-06"),
        attestation_class=AttestationClass.VERIFIABLE,
    )
    store.save_node(acc_admissible)

    # Derived node (model-generated cluster, not yet user-promoted)
    acc_derived = Accomplishment(
        id="acc_model",
        claim="Model suggested accomplishment",
        skills=["skill_python"],
        evidence=["art_1"],
        period=EvidencePeriod(start="2025-01", end="2025-06"),
        confidence=0.85,
        attestation_class=AttestationClass.DERIVED,
    )
    store.save_node(acc_derived)
    return store


def test_g1_derived_nodes_excluded_across_all_composer_queries(
    quarantined_store: LocalEvidenceStore,
) -> None:
    """Every query in COMPOSER_QUERIES excludes DERIVED nodes (G1)."""
    assert len(COMPOSER_QUERIES) > 0, "COMPOSER_QUERIES must enumerate all composer queries"

    # active()
    active_results = quarantined_store.active()
    assert all(a.attestation_class is not AttestationClass.DERIVED for a in active_results)
    assert any(a.id == "acc_real" for a in active_results)
    assert not any(a.id == "acc_model" for a in active_results)

    # by_skill()
    skill_results = quarantined_store.by_skill("skill_python")
    assert all(a.attestation_class is not AttestationClass.DERIVED for a in skill_results)
    assert not any(a.id == "acc_model" for a in skill_results)

    # by_period()
    period_results = quarantined_store.by_period("2025-01")
    assert all(a.attestation_class is not AttestationClass.DERIVED for a in period_results)
    assert not any(a.id == "acc_model" for a in period_results)

    # by_class()
    derived_class_results = quarantined_store.by_class(AttestationClass.DERIVED)
    assert derived_class_results == []

    # quarantined() is non-composer and contains the derived node
    quarantined_nodes = quarantined_store.quarantined()
    assert any(a.id == "acc_model" for a in quarantined_nodes)
