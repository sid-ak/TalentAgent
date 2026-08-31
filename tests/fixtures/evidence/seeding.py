"""Shared seeding helpers for evidence graph fixture profiles (Issue #10).

Provides deterministic loading of Profile A (artifact-backed) and Profile B (non-engineering,
purely statement-backed) into any EvidenceStore backend.
"""

from __future__ import annotations

import json
from pathlib import Path

from talentagent.evidence.graph import (
    Edge,
)
from talentagent.evidence.store import (
    EvidenceStore,
    _node_from_dict,
)

EVIDENCE_FIXTURE_ROOT = Path(__file__).parent
PROFILE_A_DIR = EVIDENCE_FIXTURE_ROOT / "profile_a"
PROFILE_B_DIR = EVIDENCE_FIXTURE_ROOT / "profile_b"


def seed_profile_a(store: EvidenceStore) -> None:
    """Seed Profile A (repository-backed verifiable graph) into store."""
    nodes_dir = PROFILE_A_DIR / "nodes"
    for p in sorted(nodes_dir.glob("*.json")):
        data = json.loads(p.read_text())
        node = _node_from_dict(data)
        store.save_node(node)

    edges_file = PROFILE_A_DIR / "edges.jsonl"
    if edges_file.exists():
        for line in edges_file.read_text().splitlines():
            if line.strip():
                edge = Edge.model_validate_json(line)
                store.save_edge(edge)


def seed_profile_b(store: EvidenceStore) -> None:
    """Seed Profile B (non-engineering, elicited statements only) into store."""
    nodes_dir = PROFILE_B_DIR / "nodes"
    for p in sorted(nodes_dir.glob("*.json")):
        data = json.loads(p.read_text())
        node = _node_from_dict(data)
        store.save_node(node)

    edges_file = PROFILE_B_DIR / "edges.jsonl"
    if edges_file.exists():
        for line in edges_file.read_text().splitlines():
            if line.strip():
                edge = Edge.model_validate_json(line)
                store.save_edge(edge)
