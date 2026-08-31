"""The completion figure the Spike A gate is measured against.

The definition matters more than the arithmetic, and getting it wrong in either direction makes the
90% threshold meaningless.

A form is complete when every field that should hold a value holds one. The map fills the standard
fields every posting on a platform shares; the bounded fallback fills the employer-authored ones,
which carry no identity a map could key on in advance (ADR-0008). Both count towards completion,
because both are Pass 2 doing its job.

Two exclusions, and only two. Fields the map deliberately declined — voluntary demographic
questions — are out of the denominator, because filling them is not a thing the system should do and
counting them as failures would push towards doing it. Fields still hidden behind an unanswered
conditional are out too, since they are not yet part of the form.

The share the map handled alone is reported separately as `deterministic_share`. It is the more
diagnostic number: a falling deterministic share with a steady completion rate means the platform
changed its DOM and the fallback is quietly papering over it.
"""

from __future__ import annotations

from dataclasses import dataclass

from talentagent.ats.fieldmap import MissReason
from talentagent.ats.resolver import Resolution


@dataclass(frozen=True)
class Completion:
    """How much of one form Pass 2 filled, and by which route.

    Attributes:
        by_map: Fields the deterministic field map resolved.
        by_fallback: Fields the bounded model fallback answered.
        unfilled: Fields that should hold a value and do not.
        declined: Fields the map recognised and deliberately declined.
        not_visible: Fields not revealed by an earlier answer, so not part of the form.
    """

    by_map: int = 0
    by_fallback: int = 0
    unfilled: int = 0
    declined: int = 0
    not_visible: int = 0

    @property
    def fillable(self) -> int:
        """Return how many fields should hold a value."""
        return self.by_map + self.by_fallback + self.unfilled

    @property
    def rate(self) -> float:
        """Return the share of fillable fields that were filled. This is the Spike A figure."""
        return (self.by_map + self.by_fallback) / self.fillable if self.fillable else 1.0

    @property
    def deterministic_share(self) -> float:
        """Return the share of fillable fields the map resolved without the model's help.

        Measured against every fillable field, not just the ones the map was expected to cover, so
        it moves when the mix moves. Diagnostic rather than a gate: a falling deterministic share
        with a steady completion rate means a platform changed its DOM and the fallback is quietly
        papering over it — which costs quota and turns a deterministic fill into a guessed one.
        """
        return self.by_map / self.fillable if self.fillable else 1.0

    def __add__(self, other: Completion) -> Completion:
        """Combine two figures, so a platform's total is the sum over its fixtures."""
        return Completion(
            by_map=self.by_map + other.by_map,
            by_fallback=self.by_fallback + other.by_fallback,
            unfilled=self.unfilled + other.unfilled,
            declined=self.declined + other.declined,
            not_visible=self.not_visible + other.not_visible,
        )


ZERO = Completion()


def from_resolution(resolution: Resolution) -> Completion:
    """Compute the figure for a form the map has resolved but the fallback has not yet touched.

    Every unmatched field counts as unfilled here, which is the honest reading before the fallback
    runs. The executor replaces those it answers (issue #15).
    """
    return Completion(
        by_map=len(resolution.resolved),
        by_fallback=0,
        unfilled=len(resolution.misses_by_reason(MissReason.NO_RULE))
        + len(resolution.misses_by_reason(MissReason.NO_VALUE)),
        declined=len(resolution.misses_by_reason(MissReason.DECLARED_UNMAPPED)),
        not_visible=len(resolution.misses_by_reason(MissReason.NOT_VISIBLE)),
    )
