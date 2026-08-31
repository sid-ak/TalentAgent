"""The complete application package schema, validation, and credit enforcement (Spec §5.1, §5.2).

Defines the durable ApplicationPackage model containing credited bullets, screening answers,
gaps, and coverage metrics. Enforces Guardrails G1 and G2 at the schema layer (Issue #25).
"""

from __future__ import annotations

import enum
from pathlib import Path
from typing import Any

from pydantic import AliasChoices, BaseModel, ConfigDict, Field, field_validator

from talentagent.evidence.graph import Accomplishment, AttestationClass
from talentagent.evidence.store import EvidenceStore, NodeNotFound


class Identity(BaseModel):
    """The applicant's personal contact details."""

    model_config = ConfigDict(extra="forbid")

    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    location: str | None = None
    current_company: str | None = None

    @property
    def full_name(self) -> str:
        """Return the name formatted as a single string for single-field forms."""
        return f"{self.first_name} {self.last_name}"


class Links(BaseModel):
    """Public profile URLs referenced on employer forms."""

    model_config = ConfigDict(extra="forbid")

    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None


class Materials(BaseModel):
    """Generated application documents and text versions."""

    model_config = ConfigDict(extra="forbid")

    resume: Path | None = None
    cover_letter: Path | None = None
    cover_letter_text: str | None = None


class CreditedBullet(BaseModel):
    """A generated accomplishment bullet point carrying explicit evidence credits (Spec §5.1)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    text: str
    credits: list[str] = Field(
        ...,
        min_length=1,
        description="Accomplishment IDs backing this bullet (Guardrail G2).",
    )
    attestation_class: AttestationClass = Field(
        ...,
        validation_alias=AliasChoices("class", "attestation_class"),
        serialization_alias="class",
    )
    artifacts: list[str] = Field(default_factory=list)
    requirement_ids: list[str] = Field(default_factory=list)

    @field_validator("credits")
    @classmethod
    def validate_non_empty_credits(cls, credits: list[str]) -> list[str]:
        """Enforce that every generated line carries at least one credit (G2)."""
        if not credits:
            raise ValueError("Every generated bullet must carry at least one credit (G2).")
        return credits


class ScreeningAnswer(BaseModel):
    """An answer to an employer screening question with supporting evidence credits (Spec §5.1)."""

    model_config = ConfigDict(extra="forbid")

    question: str
    value: str
    question_id: str | None = None
    credits: list[str] = Field(default_factory=list)


class GapAction(enum.Enum):
    """The action emitted for a requirement below sufficiency threshold (Spec §5.3)."""

    FLAG = "FLAG"
    """Partial evidence exists below threshold; reports requirement and best available evidence."""
    ELICIT = "ELICIT"
    """No usable evidence exists; emits one scoped question to elicit evidence from user."""


class Gap(BaseModel):
    """A missing or weakly evidenced requirement reported as a deliverable (Spec §5.3)."""

    model_config = ConfigDict(extra="forbid")

    requirement_id: str
    text: str
    best_available: str | None = None
    sufficiency: float
    action: GapAction
    question: str | None = None


class Coverage(BaseModel):
    """Credit coverage metrics broken down by attestation class (Spec §5.1, §5.4)."""

    model_config = ConfigDict(extra="forbid")

    total: float
    verifiable: float
    corroborated: float
    attested: float


class PackageValidationError(ValueError):
    """Raised when an application package violates schema, credit, or quarantine rules."""


class ApplicationPackage(BaseModel):
    """The full application package composed in Pass 1 and executed in Pass 2 (Spec §5.1)."""

    model_config = ConfigDict(extra="forbid", populate_by_name=True)

    posting_id: str
    identity: Identity
    links: Links = Field(default_factory=Links)
    materials: Materials = Field(default_factory=Materials)
    bullets: list[CreditedBullet] = Field(default_factory=list)
    screening_answers: list[ScreeningAnswer] = Field(default_factory=list)
    gaps: list[Gap] = Field(default_factory=list)
    coverage: Coverage | None = None
    assignment_rule_id: str | None = None

    def resolve_path(self, path: str) -> Any:
        """Return the value at a dotted package path for deterministic field map resolution.

        Raises:
            KeyError: if the path names an attribute that does not exist.
        """
        current: Any = self
        for part in path.split("."):
            if not hasattr(current, part):
                raise KeyError(f"{path!r} is not a package path; {part!r} does not exist")
            current = getattr(current, part)
        return current


def validate_package(package: ApplicationPackage, store: EvidenceStore) -> None:
    """Validate that all credits on `package` resolve to admissible nodes in `store` (G1, G2).

    Raises:
        PackageValidationError: if an uncredited line is present, a credit references a nonexistent
            node, or a credit references a DERIVED node.
    """
    for bullet in package.bullets:
        if not bullet.credits:
            raise PackageValidationError(
                f"Bullet {bullet.text!r} has no credits (Guardrail G2 violation)."
            )
        for credit_id in bullet.credits:
            try:
                node = store.get_node(credit_id)
            except (NodeNotFound, KeyError):
                raise PackageValidationError(
                    f"Bullet credits non-existent node {credit_id!r}."
                ) from None

            if not isinstance(node, Accomplishment):
                raise PackageValidationError(
                    f"Credit {credit_id!r} references node of type {type(node).__name__}; "
                    "must be an Accomplishment."
                )

            if node.attestation_class == AttestationClass.DERIVED:
                raise PackageValidationError(
                    f"Bullet credits quarantined DERIVED accomplishment {credit_id!r} "
                    "(Guardrail G1 violation)."
                )

            if bullet.attestation_class != node.attestation_class:
                raise PackageValidationError(
                    f"Bullet attestation class {bullet.attestation_class.value} does not match "
                    f"credited accomplishment {node.id} class {node.attestation_class.value}."
                )
