"""Firestore backends for PackageStore and EvidenceStore protocols (Spec §11, Issue #4).

Provides `FirestorePackageStore` and `FirestoreEvidenceStore` for persistence against a Firestore
instance or local emulator.
"""

from __future__ import annotations

from typing import Any

from talentagent.composer.package import ApplicationPackage
from talentagent.evidence.graph import (
    Accomplishment,
    Artifact,
    AttestationClass,
    Edge,
    EdgeType,
    Metric,
    Statement,
)
from talentagent.evidence.store import (
    AnyNode,
    NodeNotFound,
    _node_from_dict,
    composer_query,
)
from talentagent.state.documents import EVIDENCE_GRAPH, PACKAGES
from talentagent.state.packages import PackageNotFound


class FirestorePackageStore:
    """Firestore backend for storing and loading application packages."""

    def __init__(self, client: Any) -> None:
        """Initialize store with a Firestore client instance."""
        self.client = client
        self.collection = client.collection(PACKAGES)

    def save(self, application_id: str, package: ApplicationPackage) -> None:
        """Save an application package in Firestore."""
        doc_ref = self.collection.document(application_id)
        doc_ref.set(package.model_dump(mode="json", by_alias=True))

    def load(self, application_id: str) -> ApplicationPackage:
        """Load an application package from Firestore."""
        doc_ref = self.collection.document(application_id)
        snapshot = doc_ref.get()
        if not snapshot.exists:
            raise PackageNotFound(application_id)
        data = snapshot.to_dict() or {}
        return ApplicationPackage.model_validate(data)

    def record_capture(self, application_id: str, artifact: str, completion: float) -> None:
        """Record the capture artifact pointer and completion rate on an existing package."""
        doc_ref = self.collection.document(application_id)
        doc_ref.update({"capture_artifact": artifact, "completion_rate": completion})


class FirestoreEvidenceStore:
    """Firestore backend for the evidence graph."""

    def __init__(self, client: Any) -> None:
        """Initialize store with a Firestore client instance."""
        self.client = client
        self.nodes_collection = client.collection(EVIDENCE_GRAPH)
        self.edges_collection = client.collection(f"{EVIDENCE_GRAPH}_edges")

    def save_node(self, node: AnyNode) -> None:
        """Save a node into the evidence graph collection."""
        doc_id = node.id if not isinstance(node, Metric) or node.id else f"metric_{node.name}"
        self.nodes_collection.document(doc_id).set(node.model_dump(mode="json", by_alias=True))

    def get_node(self, node_id: str) -> AnyNode:
        """Retrieve a node from the evidence graph collection."""
        doc = self.nodes_collection.document(node_id).get()
        if not doc.exists:
            raise NodeNotFound(node_id)
        data = doc.to_dict() or {}
        return _node_from_dict(data)

    def save_edge(self, edge: Edge) -> None:
        """Save an edge into the edges subcollection."""
        edge_id = f"{edge.source_id}_{edge.edge_type.value}_{edge.target_id}"
        self.edges_collection.document(edge_id).set(edge.model_dump(mode="json"))

    def get_edges(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        edge_type: EdgeType | None = None,
    ) -> list[Edge]:
        """Retrieve edges matching criteria."""
        query = self.edges_collection
        if source_id is not None:
            query = query.where("source_id", "==", source_id)
        if target_id is not None:
            query = query.where("target_id", "==", target_id)
        if edge_type is not None:
            query = query.where("edge_type", "==", edge_type.value)

        edges: list[Edge] = []
        for doc in query.stream():
            edges.append(Edge.model_validate(doc.to_dict()))
        return edges

    def _all_accomplishments(self) -> list[Accomplishment]:
        """Return all Accomplishments in the store."""
        results: list[Accomplishment] = []
        for doc in self.nodes_collection.stream():
            data = doc.to_dict()
            if "claim" in data:
                results.append(Accomplishment.model_validate(data))
        return results

    def _superseded_ids(self) -> set[str]:
        """Return IDs of superseded accomplishments."""
        superseded: set[str] = set()
        for e in self.get_edges(edge_type=EdgeType.SUPERSEDES):
            superseded.add(e.target_id)
        return superseded

    @composer_query
    def active(self) -> list[Accomplishment]:
        """Return active admissible accomplishments."""
        superseded = self._superseded_ids()
        return [
            acc
            for acc in self._all_accomplishments()
            if acc.attestation_class is not AttestationClass.DERIVED and acc.id not in superseded
        ]

    def history(self) -> list[Accomplishment]:
        """Return all non-derived accomplishments including superseded."""
        return [
            acc
            for acc in self._all_accomplishments()
            if acc.attestation_class is not AttestationClass.DERIVED
        ]

    def quarantined(self) -> list[Accomplishment]:
        """Return quarantined DERIVED accomplishments."""
        return [
            acc
            for acc in self._all_accomplishments()
            if acc.attestation_class is AttestationClass.DERIVED
        ]

    @composer_query
    def by_skill(self, skill_id: str) -> list[Accomplishment]:
        """Return active accomplishments demonstrating `skill_id`."""
        direct = {acc.id for acc in self.active() if skill_id in acc.skills}
        for e in self.get_edges(target_id=skill_id, edge_type=EdgeType.DEMONSTRATES):
            direct.add(e.source_id)
        return [acc for acc in self.active() if acc.id in direct]

    @composer_query
    def by_period(self, start: str, end: str | None = None) -> list[Accomplishment]:
        """Return active accomplishments in period."""
        active_nodes = self.active()
        results: list[Accomplishment] = []
        for acc in active_nodes:
            if acc.period is None:
                continue
            if acc.period.start >= start and (
                end is None or (acc.period.end is None or acc.period.end <= end)
            ):
                results.append(acc)
        return results

    @composer_query
    def by_class(self, attestation_class: AttestationClass) -> list[Accomplishment]:
        """Return active accomplishments of specified class."""
        if attestation_class is AttestationClass.DERIVED:
            return []
        return [acc for acc in self.active() if acc.attestation_class == attestation_class]

    @composer_query
    def supporting_evidence(self, accomplishment_id: str) -> list[Artifact | Statement]:
        """Return supporting evidence nodes for accomplishment."""
        acc = self.get_node(accomplishment_id)
        if not isinstance(acc, Accomplishment):
            raise NodeNotFound(f"Node {accomplishment_id} is not an Accomplishment")

        evidence_nodes: list[Artifact | Statement] = []
        for ev_id in acc.evidence:
            node = self.get_node(ev_id)
            if isinstance(node, (Artifact, Statement)):
                evidence_nodes.append(node)
        return evidence_nodes
