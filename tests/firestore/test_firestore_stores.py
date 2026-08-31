"""Tests for FirestorePackageStore and FirestoreEvidenceStore (Issue #4)."""

from unittest.mock import MagicMock

import pytest
from talentagent.ats.package import ApplicationPackage, Identity
from talentagent.evidence.graph import (
    Artifact,
    ArtifactSubtype,
    Edge,
    EdgeType,
    NodeType,
)
from talentagent.state.firestore import FirestoreEvidenceStore, FirestorePackageStore
from talentagent.state.packages import PackageNotFound


def test_firestore_package_store_save_load_capture() -> None:
    """FirestorePackageStore saves, loads, and records capture properly."""
    mock_client = MagicMock()
    mock_collection = MagicMock()
    mock_doc = MagicMock()
    mock_client.collection.return_value = mock_collection
    mock_collection.document.return_value = mock_doc

    store = FirestorePackageStore(mock_client)
    pkg = ApplicationPackage(
        posting_id="job_1",
        identity=Identity(first_name="Ada", last_name="Lovelace", email="ada@example.com"),
    )

    # Save
    store.save("app_1", pkg)
    mock_collection.document.assert_called_with("app_1")
    mock_doc.set.assert_called_once()

    # Load success
    mock_snapshot = MagicMock()
    mock_snapshot.exists = True
    mock_snapshot.to_dict.return_value = pkg.model_dump(mode="json")
    mock_doc.get.return_value = mock_snapshot

    loaded = store.load("app_1")
    assert loaded.posting_id == "job_1"
    assert loaded.identity.first_name == "Ada"

    # Load not found
    mock_snapshot.exists = False
    with pytest.raises(PackageNotFound):
        store.load("app_missing")

    # Record capture
    store.record_capture("app_1", "artifact_path", 0.95)
    mock_doc.update.assert_called_with(
        {"capture_artifact": "artifact_path", "completion_rate": 0.95}
    )


def test_firestore_evidence_store_operations() -> None:
    """FirestoreEvidenceStore saves and retrieves nodes and edges."""
    mock_client = MagicMock()
    mock_nodes_col = MagicMock()
    mock_edges_col = MagicMock()
    mock_node_doc = MagicMock()
    mock_edge_doc = MagicMock()

    def get_col(name: str) -> MagicMock:
        if name == "evidence_graph":
            return mock_nodes_col
        return mock_edges_col

    mock_client.collection.side_effect = get_col
    mock_nodes_col.document.return_value = mock_node_doc
    mock_edges_col.document.return_value = mock_edge_doc

    store = FirestoreEvidenceStore(mock_client)

    # Save node
    art = Artifact(id="art_1", subtype=ArtifactSubtype.PR, title="PR 1")
    store.save_node(art)
    mock_nodes_col.document.assert_called_with("art_1")
    mock_node_doc.set.assert_called_once()

    # Save edge
    edge = Edge(
        source_id="art_1",
        source_type=NodeType.ARTIFACT,
        target_id="acc_1",
        target_type=NodeType.ACCOMPLISHMENT,
        edge_type=EdgeType.EVIDENCES,
    )
    store.save_edge(edge)
    mock_edges_col.document.assert_called_with("art_1_evidences_acc_1")
    mock_edge_doc.set.assert_called_once()
