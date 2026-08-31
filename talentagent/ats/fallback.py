"""The bounded model fallback for unmapped custom fields.

The field map covers the fields every posting on a platform shares. Employer-authored screening
questions are per-posting and carry no identity a map could key on in advance, so a fallback is
required — and narrow is the operative word (ADR-0008).

Four bounds, and each closes a different hole:

Reachability. It is called only with fields the resolver reported as NO_RULE. A field the map
resolved, or one it deliberately declined, is never offered — the executor enforces that, and this
module re-checks it, because the boundary is the point of the design.

Input. It sees the field's own label and options plus the composed package, and never the raw page.
Passing the DOM would put third-party text into the instruction context (G7).

Confidence. Below the threshold the field is left empty and recorded as a miss, rather than filled
with a guess. An unanswered question a reviewer can see is better than a confident wrong answer they
cannot.

Volume. A per-run cap, so a badly matched map degrades into a visible halt rather than quietly
draining the Gemini Flash daily quota, which is the tightest margin in the design (Architecture 8).
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from talentagent.ats.package import ApplicationPackage
from talentagent.ats.resolver import Missed
from talentagent.models.client import ModelClient

#: Answers below this are not written. Chosen so a model that is guessing leaves the field empty.
DEFAULT_CONFIDENCE_THRESHOLD = 0.6

#: Most invocations one run may make. A form needing more than this has a map problem, not a
#: question problem.
DEFAULT_MAX_INVOCATIONS = 12

#: Names the response schema the model must satisfy. A response failing it is a failure.
SCHEMA = "ats_custom_field_v1"

_PROMPT = (
    "Answer one employer screening question using only the applicant's composed application "
    "package. Do not introduce any fact the package does not contain. If the package does not "
    "support an answer, return a confidence of 0."
)


class FallbackCapExceeded(RuntimeError):
    """Raised when a run needs more fallback invocations than its cap allows."""

    def __init__(self, cap: int) -> None:
        """Record the cap that was hit."""
        self.cap = cap
        super().__init__(
            f"The bounded fallback hit its per-run cap of {cap} invocations. That many unmapped "
            f"fields means the field map no longer matches the platform, so this halts with a "
            f"partial capture rather than continuing (ADR-0008)."
        )


class FallbackReachedMappedField(RuntimeError):
    """Raised if the fallback is handed a field the map resolved or deliberately declined."""

    def __init__(self, name: str) -> None:
        """Name the field that should not have been offered."""
        self.name = name
        super().__init__(
            f"{name!r} was not reported as unmatched, so the bounded fallback must not see it."
        )


@dataclass
class FallbackInvocation:
    """One question the model answered, retained for the run artifact.

    Every invocation is surfaced in the capture so a reviewer sees exactly which answers were not
    deterministic — which is the difference between a form a human can check and one they must
    trust.

    Attributes:
        field_name: The control the answer was written into.
        question: The question as the form asked it.
        answer: What the model produced.
        confidence: Its own reported confidence.
        accepted: Whether the answer met the threshold and was written.
    """

    field_name: str
    question: str
    answer: str
    confidence: float
    accepted: bool


@dataclass
class BoundedFallback:
    """Answers unmapped custom questions from the package, within declared bounds."""

    client: ModelClient
    package: ApplicationPackage
    confidence_threshold: float = DEFAULT_CONFIDENCE_THRESHOLD
    max_invocations: int = DEFAULT_MAX_INVOCATIONS
    invocations: list[FallbackInvocation] = field(default_factory=list)

    @property
    def accepted(self) -> tuple[FallbackInvocation, ...]:
        """Return the invocations whose answers were written."""
        return tuple(i for i in self.invocations if i.accepted)

    @property
    def rejected(self) -> tuple[FallbackInvocation, ...]:
        """Return the invocations left empty because confidence was too low."""
        return tuple(i for i in self.invocations if not i.accepted)

    def _question_for(self, miss: Missed) -> str:
        """Return the question text, taken from the field's own label rather than from the page."""
        return miss.field.label or miss.field.aria or miss.field.name

    def _package_context(self) -> dict[str, Any]:
        """Return the package fields an answer may draw on.

        Deliberately the composed package and nothing else. Everything here originated with the
        user or with Pass 1's evidence-constrained composition, so the fallback selects rather
        than introduces.
        """
        return {
            "screening_answers": [
                {"question": a.question, "value": a.value} for a in self.package.screening_answers
            ],
            "identity": {
                "location": self.package.identity.location,
                "current_company": self.package.identity.current_company,
            },
            "cover_letter_text": self.package.materials.cover_letter_text,
        }

    def __call__(self, pending: tuple[Missed, ...]) -> dict[str, str]:
        """Answer as many of `pending` as the package supports.

        Raises:
            FallbackReachedMappedField: if a field was offered that the map did not report
                unmatched.
            FallbackCapExceeded: if answering them all would exceed the per-run cap.
        """
        for miss in pending:
            if not miss.eligible_for_fallback:
                raise FallbackReachedMappedField(miss.name)

        if len(self.invocations) + len(pending) > self.max_invocations:
            raise FallbackCapExceeded(self.max_invocations)

        answers: dict[str, str] = {}
        for miss in pending:
            question = self._question_for(miss)
            response = self.client.tier_two(
                _PROMPT,
                {
                    "question": question,
                    "options": list(miss.field.options),
                    "kind": miss.field.kind,
                    "package": self._package_context(),
                },
                SCHEMA,
            )
            answer = str(response.get("answer", ""))
            confidence = float(response.get("confidence", 0.0))
            accepted = bool(answer) and confidence >= self.confidence_threshold
            if accepted and miss.field.options and answer not in miss.field.options:
                # The model produced something outside the control's own option list. Treated as a
                # low-confidence answer rather than written and rejected by the page.
                accepted = False
            self.invocations.append(
                FallbackInvocation(
                    field_name=miss.name,
                    question=question,
                    answer=answer,
                    confidence=confidence,
                    accepted=accepted,
                )
            )
            if accepted:
                answers[miss.name] = answer
        return answers
