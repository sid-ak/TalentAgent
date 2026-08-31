"""Node and edge types, attestation classes, and invariants for the evidence graph (Spec §3).

The evidence graph is the single admissible source of claims for composition. Every node has a
typed attestation class (Spec §3.2) that records its provenance, and every accomplishment carries
non-empty references to underlying artifacts or user statements (Invariant 1).
"""

from __future__ import annotations

import enum
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator


class NodeType(enum.Enum):
    """The entity types supported by the evidence graph (Spec §3.1)."""

    ARTIFACT = "artifact"
    """A concrete work product: commit, pull request, design doc, or ticket."""
    STATEMENT = "statement"
    """The user's dated assertion, stored in the user's own words."""
    ACCOMPLISHMENT = "accomplishment"
    """A claim supported by at least one artifact or statement."""
    SKILL = "skill"
    """A canonical capability or technology."""
    METRIC = "metric"
    """A typed quantitative measure of outcome or scope."""


class ArtifactSubtype(enum.Enum):
    """The category of an ingested artifact (Spec §3.1)."""

    COMMIT = "commit"
    """A version control commit."""
    PR = "pr"
    """A pull request or merge request."""
    DOC = "doc"
    """A design document or technical specification."""
    DESIGN = "design"
    """A design file or architectural blueprint."""
    TICKET = "ticket"
    """An issue or task tracker ticket."""
    COURSE = "course"
    """A course or certification completion record."""
    CALENDAR_EVENT = "calendar_event"
    """A calendar entry indicating participation or presentation."""


class AttestationClass(enum.Enum):
    """Graded provenance levels for evidence graph nodes (Spec §3.2, Appendix A)."""

    VERIFIABLE = "verifiable"
    """Resolves to a source a third party can inspect (e.g. public repository)."""
    CORROBORATED = "corroborated"
    """Private artifact the user holds and can produce on request."""
    ATTESTED = "attested"
    """The user's dated statement; no external artifact."""
    DERIVED = "derived"
    """Proposed by the model from other evidence; quarantined until user confirmation."""

    @property
    def admissible(self) -> bool:
        """Return whether nodes of this class may be selected by the composer (Appendix A)."""
        return self is not AttestationClass.DERIVED

    @property
    def inspectable(self) -> bool:
        """Return whether a third party can directly inspect the underlying source."""
        return self is AttestationClass.VERIFIABLE

    @property
    def artifact_exists(self) -> bool:
        """Return whether a distinct artifact object backs this claim."""
        return self in (AttestationClass.VERIFIABLE, AttestationClass.CORROBORATED)


class EdgeType(enum.Enum):
    """The directed relationship types supported by the evidence graph (Spec §3.1)."""

    EVIDENCES = "evidences"
    """An Artifact or Statement evidences an Accomplishment."""
    DEMONSTRATES = "demonstrates"
    """An Accomplishment demonstrates a Skill."""
    QUANTIFIES = "quantifies"
    """A Metric quantifies an Accomplishment."""
    SUPERSEDES = "supersedes"
    """An Accomplishment supersedes an earlier Accomplishment."""

    @property
    def allowed_connections(self) -> set[tuple[NodeType, NodeType]]:
        """Return the set of valid (source_type, target_type) pairs for this edge type."""
        match self:
            case EdgeType.EVIDENCES:
                return {
                    (NodeType.ARTIFACT, NodeType.ACCOMPLISHMENT),
                    (NodeType.STATEMENT, NodeType.ACCOMPLISHMENT),
                }
            case EdgeType.DEMONSTRATES:
                return {(NodeType.ACCOMPLISHMENT, NodeType.SKILL)}
            case EdgeType.QUANTIFIES:
                return {(NodeType.METRIC, NodeType.ACCOMPLISHMENT)}
            case EdgeType.SUPERSEDES:
                return {(NodeType.ACCOMPLISHMENT, NodeType.ACCOMPLISHMENT)}


class InvalidEdgeError(ValueError):
    """Raised when an edge connects incompatible node types."""


class Edge(BaseModel):
    """A directed relationship between two nodes in the evidence graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    source_id: str
    source_type: NodeType
    target_id: str
    target_type: NodeType
    edge_type: EdgeType

    @field_validator("edge_type")
    @classmethod
    def validate_edge_type_connectivity(cls, edge_type: EdgeType, info: Any) -> EdgeType:
        """Assert that the source and target node types are legal for this edge type."""
        data = info.data
        source_type = data.get("source_type")
        target_type = data.get("target_type")
        if (
            source_type is not None
            and target_type is not None
            and (source_type, target_type) not in edge_type.allowed_connections
        ):
            raise InvalidEdgeError(
                f"Edge type {edge_type.value} cannot connect {source_type.value} -> "
                f"{target_type.value}. Allowed: {edge_type.allowed_connections}"
            )
        return edge_type


class EvidencePeriod(BaseModel):
    """A time interval associated with an accomplishment or artifact."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    start: str
    end: str | None = None


class StatementSource(BaseModel):
    """The verbatim content and elicitation metadata of a user statement (Spec §3.3)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    raw: str
    """The user's verbatim statement, stored unmodified (Spec §3.4 Invariant 3)."""
    elicited_by: str | None = None
    asserted_at: str | None = None
    artifact_producible: bool = False


class Metric(BaseModel):
    """A measured outcome or scope indicator attached to an accomplishment (Spec §3.3)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str | None = None
    name: str
    value: float | int | None = None
    delta: float | int | None = None
    unit: str
    basis: str


class Artifact(BaseModel):
    """A concrete work product node in the evidence graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    subtype: ArtifactSubtype
    title: str
    url: str | None = None
    source: str | None = None
    period: EvidencePeriod | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class Statement(BaseModel):
    """A user statement node in the evidence graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    statement: StatementSource
    period: EvidencePeriod | None = None


class Skill(BaseModel):
    """A canonical skill or technology node in the evidence graph."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    name: str
    category: str | None = None


class Accomplishment(BaseModel):
    """A claim supported by underlying evidence (Spec §3.3)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    id: str
    claim: str
    skills: list[str] = Field(default_factory=list)
    metrics: list[Metric] = Field(default_factory=list)
    evidence: list[str] = Field(
        ...,
        min_length=1,
        description="List of artifact or statement IDs backing this accomplishment (Invariant 1).",
    )
    attestation_class: AttestationClass = Field(
        ...,
        validation_alias=AliasChoices("class", "attestation_class"),
        serialization_alias="class",
    )
    period: EvidencePeriod | None = None
    confidence: float | None = None
    derived_by: str | None = None
    statement: StatementSource | None = None

    @field_validator("evidence")
    @classmethod
    def validate_non_empty_provenance(cls, evidence: list[str]) -> list[str]:
        """Assert that evidence is non-empty (Spec §3.4 Invariant 1)."""
        if not evidence:
            raise ValueError("Accomplishment must have non-empty evidence list (Invariant 1).")
        return evidence
