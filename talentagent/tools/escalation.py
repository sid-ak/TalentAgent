"""Escalation as a defined terminal outcome, not an error path (Spec 2.2, 8.5).

Any agent may terminate with ESCALATE in place of a result. Because it is an outcome rather than an
exception, its rate per decision point is a reported metric: a spike localises the weak contract
rather than merely signalling that something went wrong somewhere (Spec 12).
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class Escalation:
    """A terminal outcome handing a decision back to the human.

    Attributes:
        decision_point: Which decision could not be made, e.g. `pipeline.transition`. This is the
            unit the escalation-rate metric is grouped by.
        reason: Why, in a form a human reading the activity feed can act on.
        payload: Whatever the human needs to make the decision.
    """

    decision_point: str
    reason: str
    payload: dict[str, Any] = field(default_factory=dict)


class EscalationLog:
    """Counts escalations per decision point, so the reported rate is a read not an estimate."""

    def __init__(self) -> None:
        """Start with no recorded decisions."""
        self._decisions: Counter[str] = Counter()
        self._escalations: Counter[str] = Counter()

    def record_decision(self, decision_point: str) -> None:
        """Note that a decision was reached at `decision_point`."""
        self._decisions[decision_point] += 1

    def record_escalation(self, escalation: Escalation) -> None:
        """Note that `decision_point` escalated instead of deciding."""
        self._decisions[escalation.decision_point] += 1
        self._escalations[escalation.decision_point] += 1

    def rate(self, decision_point: str) -> float:
        """Return the share of decisions at `decision_point` that escalated."""
        total = self._decisions[decision_point]
        return self._escalations[decision_point] / total if total else 0.0

    def rates(self) -> dict[str, float]:
        """Return the escalation rate for every decision point seen."""
        return {point: self.rate(point) for point in self._decisions}
