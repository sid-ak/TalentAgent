"""What one Pass 2 run carries when it stops early.

A run ends early for two reasons — the page is not what the map expects, or the bounded fallback
hit its cap — and both mean the same thing to a caller: stop, and write down what was filled before
stopping (Architecture 7).

The partial fill travels on the exception rather than being reconstructed by each caller, because
a halt recorded as an empty result reads as a form with nothing left to fill, which is the opposite
of what happened. One base class here means a caller catches the halt once and reads the same
attribute whichever of the two it was.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

if TYPE_CHECKING:  # pragma: no cover - import only for annotations
    from talentagent.ats.executor import FillResult


class HaltedRun(RuntimeError):
    """A run that stopped early, carrying the fill as it stood at that moment.

    Attributes:
        partial: What the run had filled when it stopped. Set by the executor as the halt passes
            through it, so it is None only for a halt raised outside a fill.
    """

    partial: FillResult | None = None

    def partial_fill(self) -> FillResult:
        """Return the fill as it stood when the run stopped.

        Raises:
            RuntimeError: if the halt never passed through a fill and so carries nothing. A halt
                raised inside `fill_form` always carries one, which is every halt a caller of the
                worker or the gate can see.
        """
        if self.partial is None:
            raise RuntimeError(f"this halt carries no partial fill to record: {self}")
        return self.partial
