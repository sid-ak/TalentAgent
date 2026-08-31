"""Coverage breakdown by attestation class and credit trace-through (Spec §5.4, Issue #27).

Provides calculation of candidate coverage fractions across attestation classes and verification
that every credited bullet traces completely through to underlying artifacts or raw statements.
"""

from __future__ import annotations

from talentagent.composer.package import ApplicationPackage, Coverage, CreditedBullet
from talentagent.evidence.graph import (
    Accomplishment,
    Artifact,
    AttestationClass,
    Statement,
)
from talentagent.evidence.store import EvidenceStore


def compute_coverage(package: ApplicationPackage, store: EvidenceStore) -> Coverage:
    """Compute coverage metrics across attestation classes for `package` (Spec §5.4)."""
    if not package.bullets:
        return Coverage(total=0.0, verifiable=0.0, corroborated=0.0, attested=0.0)

    total_bullets = len(package.bullets)
    verifiable_count = sum(
        1 for b in package.bullets if b.attestation_class == AttestationClass.VERIFIABLE
    )
    corroborated_count = sum(
        1 for b in package.bullets if b.attestation_class == AttestationClass.CORROBORATED
    )
    attested_count = sum(
        1 for b in package.bullets if b.attestation_class == AttestationClass.ATTESTED
    )

    return Coverage(
        total=round(1.0, 2),
        verifiable=round(verifiable_count / total_bullets, 2),
        corroborated=round(corroborated_count / total_bullets, 2),
        attested=round(attested_count / total_bullets, 2),
    )


def trace_bullet_evidence(
    bullet: CreditedBullet,
    store: EvidenceStore,
) -> list[Artifact | Statement]:
    """Trace every credit on `bullet` to its underlying artifact or statement provenance.

    Raises:
        NodeNotFound: if a credit or underlying evidence node cannot be found.
        RuntimeError: if a credit references a non-accomplishment or orphaned node.
    """
    provenance_nodes: list[Artifact | Statement] = []
    seen_ids: set[str] = set()

    for credit_id in bullet.credits:
        acc = store.get_node(credit_id)
        if not isinstance(acc, Accomplishment):
            raise RuntimeError(f"Credit {credit_id} is not an Accomplishment.")

        supporting = store.supporting_evidence(acc.id)
        for supp in supporting:
            if supp.id not in seen_ids:
                provenance_nodes.append(supp)
                seen_ids.add(supp.id)

    return provenance_nodes
