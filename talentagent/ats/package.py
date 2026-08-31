"""The slice of the application package Pass 2 consumes.

Pass 1 composes the credited bullets, screening answers, gaps, and coverage that make up the full
package in Spec 5.1; that arrives with issue #24. Pass 2 needs only the values that go into form
fields, so this is deliberately the narrow view — the two passes are separate precisely so the
mechanical half does not depend on the reasoning half (ADR-0008).
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from pydantic import BaseModel, Field


class Identity(BaseModel):
    """The applicant's own details, which are facts rather than claims and carry no credits."""

    first_name: str
    last_name: str
    email: str
    phone: str | None = None
    location: str | None = None
    current_company: str | None = None

    @property
    def full_name(self) -> str:
        """Return the name as platforms wanting a single field expect it."""
        return f"{self.first_name} {self.last_name}"


class Links(BaseModel):
    """Public profile URLs the platforms ask for by name."""

    linkedin: str | None = None
    github: str | None = None
    portfolio: str | None = None


class Materials(BaseModel):
    """The generated documents and their plain-text forms.

    Attributes:
        resume: Path to the rendered resume, uploaded to the platform's attachment control.
        cover_letter: Path to the rendered cover letter, where the platform takes a file.
        cover_letter_text: The same content, where the platform takes a textarea instead.
    """

    resume: Path | None = None
    cover_letter: Path | None = None
    cover_letter_text: str | None = None


class ScreeningAnswer(BaseModel):
    """One answer to an employer-authored question.

    Attributes:
        question: The question as the form asked it, kept so the fallback matches on it.
        value: The answer, composed in Pass 1 from evidence.
        credits: Accomplishment ids backing the answer. Empty here only until #24 lands; the
            credit contract in Spec 5.2 is enforced at the package schema layer by issue #25.
    """

    question: str
    value: str
    credits: list[str] = Field(default_factory=list)


class ApplicationPackage(BaseModel):
    """What Pass 2 fills a form from.

    Frozen alongside the capture at the end of a run, so a later regeneration cannot be confused
    with what was actually filled (Spec 11).
    """

    posting_id: str
    identity: Identity
    links: Links = Field(default_factory=Links)
    materials: Materials = Field(default_factory=Materials)
    screening_answers: list[ScreeningAnswer] = Field(default_factory=list)

    def resolve_path(self, path: str) -> Any:
        """Return the value at a dotted package path, or None if it is unset.

        Raises:
            KeyError: if the path names an attribute the package does not have, so a typo in a
                field map fails loudly at fill time rather than filling a field with nothing.
        """
        current: Any = self
        for part in path.split("."):
            if not hasattr(current, part):
                raise KeyError(f"{path!r} is not a package path; {part!r} does not exist")
            current = getattr(current, part)
        return current
