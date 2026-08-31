"""Firestore collections, write ownership, and document envelopes (Architecture §5.1, Spec §11).

Defines the six durable collections, the single-writer table mapping collection paths to component
claims, and timeline metadata models ensuring every mutation is auditable.
"""

from __future__ import annotations

import datetime
from typing import Any

from pydantic import BaseModel, ConfigDict, Field

APPLICATIONS = "applications"
"""Application records: state machine, timeline, and transition evidence (owned by pipeline)."""

EVIDENCE_GRAPH = "evidence_graph"
"""Accomplishments, artifacts, statements, skills, and metrics (owned by evidence agent)."""

PACKAGES = "packages"
"""Composed application packages, credited bullets, and screening answers (owned by composer)."""

HYPOTHESES = "hypotheses"
"""Analytic hypotheses, active experiments, and findings (owned by analyst)."""

ASSIGNMENT_RULES = "assignment_rules"
"""Exploration and exploitation routing rules registered by the analyst (owned by analyst)."""

OUTCOMES = "outcomes"
"""Append-only outcome event log and eligibility corpus (created by pipeline, immutable)."""

COLLECTIONS: tuple[str, ...] = (
    APPLICATIONS,
    EVIDENCE_GRAPH,
    PACKAGES,
    HYPOTHESES,
    ASSIGNMENT_RULES,
    OUTCOMES,
)
"""The six durable operational collections in Firestore."""

WRITE_OWNERSHIP: dict[str, str] = {
    APPLICATIONS: "pipeline",
    EVIDENCE_GRAPH: "evidence",
    PACKAGES: "composer",
    HYPOTHESES: "analyst",
    ASSIGNMENT_RULES: "analyst",
    OUTCOMES: "pipeline",
}
"""Maps collection names to the component claim permitted to write to them (Architecture §5.1)."""


class TimelineEntry(BaseModel):
    """A transition record appended to an application timeline (Spec §4.2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    from_state: str
    to_state: str
    at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())
    evidence_message_id: str | None = None
    confidence: float = 1.0
    decided_by: str


class DocumentEnvelope(BaseModel):
    """Envelope wrapping operational documents with mutation timeline and audit metadata."""

    model_config = ConfigDict(extra="forbid")

    id: str
    collection: str
    data: dict[str, Any]
    timeline: list[TimelineEntry] = Field(default_factory=list)
    created_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())
    updated_at: str = Field(default_factory=lambda: datetime.datetime.now(datetime.UTC).isoformat())

    def append_timeline(self, entry: TimelineEntry) -> None:
        """Append a transition entry and advance updated_at timestamp."""
        self.timeline.append(entry)
        self.updated_at = datetime.datetime.now(datetime.UTC).isoformat()
