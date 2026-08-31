"""Evidence graph store protocol, local JSON backend, and composer query boundary (Spec §3).

Defines the `EvidenceStore` protocol, the local filesystem implementation, and the `@composer_query`
quarantine choke point ensuring no `DERIVED` accomplishment reaches the composer
(Spec §3.4 Invariant 2, Guardrail G1).
"""

from __future__ import annotations

import functools
import json
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

from talentagent.evidence.graph import (
    Accomplishment,
    Artifact,
    AttestationClass,
    Edge,
    EdgeType,
    Metric,
    Skill,
    Statement,
)

COMPOSER_QUERIES: list[str] = []
"""Registry of method names reachable by the composer, asserted by guardrail tests (G1)."""


def composer_query[F: Callable[..., Any]](func: F) -> F:
    """Decorator registering a store query as composer-reachable and asserting no DERIVED leakage.

    Every query decorated with this choke point has its output asserted to contain zero `DERIVED`
    accomplishments before returning.
    """
    method_name = func.__name__
    if method_name not in COMPOSER_QUERIES:
        COMPOSER_QUERIES.append(method_name)

    @functools.wraps(func)
    def wrapper(*args: Any, **kwargs: Any) -> Any:
        result = func(*args, **kwargs)
        if isinstance(result, list):
            for item in result:
                if (
                    isinstance(item, Accomplishment)
                    and item.attestation_class is AttestationClass.DERIVED
                ):
                    raise RuntimeError(
                        f"Quarantine violation (G1): DERIVED accomplishment {item.id} "
                        f"leaked through composer query {method_name}."
                    )
        return result

    return wrapper  # type: ignore[return-value]


class NodeNotFound(KeyError):
    """Raised when a requested graph node does not exist."""


AnyNode = Artifact | Statement | Skill | Metric | Accomplishment


@runtime_checkable
class EvidenceStore(Protocol):
    """Storage protocol for evidence graph nodes and edges."""

    def save_node(self, node: AnyNode) -> None:
        """Persist a node in the graph."""
        ...

    def get_node(self, node_id: str) -> AnyNode:
        """Retrieve a node by its identifier."""
        ...

    def save_edge(self, edge: Edge) -> None:
        """Persist an edge in the graph."""
        ...

    def active(self) -> list[Accomplishment]:
        """Return all active (non-superseded, non-derived) accomplishments."""
        ...

    def history(self) -> list[Accomplishment]:
        """Return all non-derived accomplishments including superseded ones."""
        ...

    def quarantined(self) -> list[Accomplishment]:
        """Return quarantined DERIVED accomplishments held for confirmation."""
        ...

    def by_skill(self, skill_id: str) -> list[Accomplishment]:
        """Return active admissible accomplishments demonstrating `skill_id`."""
        ...

    def by_period(self, start: str, end: str | None = None) -> list[Accomplishment]:
        """Return active admissible accomplishments within the specified time range."""
        ...

    def by_class(self, attestation_class: AttestationClass) -> list[Accomplishment]:
        """Return active accomplishments of the specified attestation class."""
        ...

    def supporting_evidence(self, accomplishment_id: str) -> list[Artifact | Statement]:
        """Return the underlying artifacts or statements evidencing `accomplishment_id`."""
        ...


def _node_from_dict(data: dict[str, Any]) -> AnyNode:
    """Parse a dictionary into the corresponding graph node model."""
    if "subtype" in data:
        return Artifact.model_validate(data)
    if "statement" in data and "claim" not in data:
        return Statement.model_validate(data)
    if "claim" in data:
        return Accomplishment.model_validate(data)
    if "unit" in data and "basis" in data:
        return Metric.model_validate(data)
    return Skill.model_validate(data)


def _get_node_id(node: AnyNode) -> str:
    """Extract the node identifier, computing a default for metrics without an explicit id."""
    if isinstance(node, Metric):
        return node.id if node.id is not None else f"metric_{node.name}"
    return node.id


class LocalEvidenceStore:
    """Filesystem-backed JSON store for offline test execution and fixtures."""

    def __init__(self, root: Path) -> None:
        """Initialize the store under the specified directory."""
        self.root = root
        self._nodes_dir = root / "nodes"
        self._edges_file = root / "edges.jsonl"

    def _ensure_dirs(self) -> None:
        """Create directories if they do not exist."""
        self._nodes_dir.mkdir(parents=True, exist_ok=True)
        self.root.mkdir(parents=True, exist_ok=True)

    def save_node(self, node: AnyNode) -> None:
        """Save a node as JSON on disk."""
        self._ensure_dirs()
        node_id = _get_node_id(node)
        node_file = self._nodes_dir / f"{node_id}.json"
        node_file.write_text(node.model_dump_json(by_alias=True, indent=2))

    def get_node(self, node_id: str) -> AnyNode:
        """Retrieve a node by identifier."""
        node_file = self._nodes_dir / f"{node_id}.json"
        if not node_file.exists():
            raise NodeNotFound(node_id)
        data = json.loads(node_file.read_text())
        return _node_from_dict(data)

    def save_edge(self, edge: Edge) -> None:
        """Append an edge to the edges JSONL file."""
        self._ensure_dirs()
        existing = self.get_edges()
        if edge not in existing:
            with self._edges_file.open("a", encoding="utf-8") as f:
                f.write(edge.model_dump_json() + "\n")

    def get_edges(
        self,
        source_id: str | None = None,
        target_id: str | None = None,
        edge_type: EdgeType | None = None,
    ) -> list[Edge]:
        """Return edges matching the filter criteria."""
        if not self._edges_file.exists():
            return []
        edges: list[Edge] = []
        for line in self._edges_file.read_text().splitlines():
            if not line.strip():
                continue
            e = Edge.model_validate_json(line)
            if source_id is not None and e.source_id != source_id:
                continue
            if target_id is not None and e.target_id != target_id:
                continue
            if edge_type is not None and e.edge_type != edge_type:
                continue
            edges.append(e)
        return edges

    def _all_accomplishments(self) -> list[Accomplishment]:
        """Return all Accomplishment nodes in the store."""
        if not self._nodes_dir.exists():
            return []
        results: list[Accomplishment] = []
        for p in sorted(self._nodes_dir.glob("*.json")):
            try:
                data = json.loads(p.read_text())
                if "claim" in data:
                    results.append(Accomplishment.model_validate(data))
            except Exception:
                continue
        return results

    def _superseded_ids(self) -> set[str]:
        """Return the set of accomplishment IDs that have been superseded."""
        superseded: set[str] = set()
        for e in self.get_edges(edge_type=EdgeType.SUPERSEDES):
            # SUPERSEDES edge: source (new accomplishment) -> target (superseded accomplishment)
            superseded.add(e.target_id)
        return superseded

    @composer_query
    def active(self) -> list[Accomplishment]:
        """Return all active (non-superseded, non-derived) accomplishments."""
        superseded = self._superseded_ids()
        return [
            acc
            for acc in self._all_accomplishments()
            if acc.attestation_class is not AttestationClass.DERIVED and acc.id not in superseded
        ]

    def history(self) -> list[Accomplishment]:
        """Return all non-derived accomplishments including superseded ones."""
        return [
            acc
            for acc in self._all_accomplishments()
            if acc.attestation_class is not AttestationClass.DERIVED
        ]

    def quarantined(self) -> list[Accomplishment]:
        """Return quarantined DERIVED accomplishments held for confirmation."""
        return [
            acc
            for acc in self._all_accomplishments()
            if acc.attestation_class is AttestationClass.DERIVED
        ]

    @composer_query
    def by_skill(self, skill_id: str) -> list[Accomplishment]:
        """Return active admissible accomplishments connected to `skill_id`."""
        direct = {acc.id for acc in self.active() if skill_id in acc.skills}
        for e in self.get_edges(target_id=skill_id, edge_type=EdgeType.DEMONSTRATES):
            direct.add(e.source_id)
        return [acc for acc in self.active() if acc.id in direct]

    @composer_query
    def by_period(self, start: str, end: str | None = None) -> list[Accomplishment]:
        """Return active admissible accomplishments overlapping with the period."""
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
        """Return active accomplishments of the specified attestation class."""
        if attestation_class is AttestationClass.DERIVED:
            return []
        return [acc for acc in self.active() if acc.attestation_class == attestation_class]

    @composer_query
    def supporting_evidence(self, accomplishment_id: str) -> list[Artifact | Statement]:
        """Return the underlying artifacts or statements evidencing `accomplishment_id`."""
        acc = self.get_node(accomplishment_id)
        if not isinstance(acc, Accomplishment):
            raise NodeNotFound(f"Node {accomplishment_id} is not an Accomplishment")

        evidence_nodes: list[Artifact | Statement] = []
        for ev_id in acc.evidence:
            node = self.get_node(ev_id)
            if isinstance(node, (Artifact, Statement)):
                evidence_nodes.append(node)
        return evidence_nodes
