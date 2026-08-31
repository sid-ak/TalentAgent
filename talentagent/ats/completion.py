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

from collections.abc import Mapping
from dataclasses import dataclass

from talentagent.ats.fieldmap import MissReason
from talentagent.ats.page import FALLBACK_SOURCE
from talentagent.ats.resolver import Resolution

FILLABLE_MISSES = (MissReason.NO_RULE, MissReason.NO_VALUE)
"""The misses that still describe a field which should hold a value, and so stay in the
denominator. The other two reasons are the two exclusions above.
"""


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
        """Return the share of fillable fields that were filled. This is the Spike A figure.

        A form with nothing to fill is complete, which is why an empty figure reads as 1.0. That
        makes an empty `Completion` a dangerous stand-in for a run that failed, so a halted run
        reports what it actually filled instead (`from_fill`, and `HaltedRun.partial`).
        """
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


def from_fill(resolution: Resolution, written: Mapping[str, str]) -> Completion:
    """Compute the figure for a form as it stands, from the values actually written into it.

    Args:
        resolution: The form re-resolved after the fill, so revealed conditionals are counted.
        written: Each field that holds a value, mapped to the source that supplied it — a package
            path, or `fallback` for a model-answered field.

    Counted from what was written rather than from the resolution alone, because the two differ
    exactly when something went wrong: a field the map resolved but the page then refused holds no
    value, and counting it as filled is how a halted run comes to report itself complete.
    """
    fillable = {item.name for item in resolution.resolved} | {
        miss.name for miss in resolution.missed if miss.reason in FILLABLE_MISSES
    }
    sources = {name: source for name, source in written.items() if name in fillable}
    by_fallback = sum(1 for source in sources.values() if source == FALLBACK_SOURCE)
    return Completion(
        by_map=len(sources) - by_fallback,
        by_fallback=by_fallback,
        unfilled=len(fillable - set(sources)),
        declined=len(resolution.misses_by_reason(MissReason.DECLARED_UNMAPPED)),
        not_visible=len(resolution.misses_by_reason(MissReason.NOT_VISIBLE)),
    )
