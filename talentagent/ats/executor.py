"""Pass 2: fill a form from a package, then stop.

The loop here exists because of one property of real forms: a field can be revealed by an earlier
answer, so a single pass over the controls enumerated at the start would miss it. The executor
re-enumerates after every pass that wrote anything, and stops when a pass reveals nothing new.

Termination is the point of the whole component. Pass 2 ends in a completed, unsubmitted form
(Spec 5.5), and there is no code path here that could do otherwise: the Page protocol has no
submit method, and the run asserts the control was untouched before it reports success.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

from talentagent.ats.completion import Completion, from_fill
from talentagent.ats.fieldmap import FieldMap, MissReason
from talentagent.ats.halt import HaltedRun
from talentagent.ats.package import ApplicationPackage
from talentagent.ats.page import FALLBACK_SOURCE, FillLog, FormField, Page
from talentagent.ats.resolver import Missed, resolve

MAX_PASSES = 4
"""How many enumerate-and-fill passes to make before concluding the form has stopped changing.
Four is comfortably above the deepest conditional chain the target platforms produce, and a
cap rather than a while-loop so a page that rewrites itself cannot spin.
"""


class FormHalted(HaltedRun):
    """Raised when a run stops early with a partial fill.

    Halting is the designed response to a surprise. A DOM change means the map's assumptions no
    longer hold, and guessing from there is how a form gets filled wrongly rather than not at all
    (Architecture 7).
    """

    def __init__(self, reason: str, field_name: str | None = None) -> None:
        """Record why the run stopped, and on which field where there is one."""
        self.reason = reason
        self.field_name = field_name
        super().__init__(f"{reason}" + (f" (field: {field_name})" if field_name else ""))


@dataclass
class FillResult:
    """What one Pass 2 run did.

    Attributes:
        completion: The figure the Spike A gate is measured against.
        log: Every value written, in order, with where it came from.
        outstanding: Fields still unfilled when the run stopped.
        rejected_answers: Fallback answers the control refused, with the reason. Kept separate
            from a plain miss because a refused answer means the model produced something, and a
            reviewer should see what.
        passes: How many enumerate-and-fill passes were needed.
        halted: Why the run stopped early, if it did.
    """

    completion: Completion
    log: FillLog = field(default_factory=FillLog)
    outstanding: tuple[Missed, ...] = ()
    rejected_answers: tuple[tuple[str, str], ...] = ()
    passes: int = 0
    halted: str | None = None

    @property
    def submitted(self) -> bool:
        """Report whether anything was submitted. Always false, and asserted per run (G3)."""
        return False


def _write(page: Page, log: FillLog, form_field: FormField, value: str, source: str) -> None:
    """Write one resolved value with the primitive its control kind calls for."""
    if form_field.is_upload:
        page.upload(form_field.name, Path(value))
    else:
        page.fill(form_field.name, value)
    log.record(form_field.name, value, source)


@dataclass
class _Run:
    """One fill in progress, and the single place a result is built from it.

    Kept as a value rather than as loose locals so the halt path and the success path report the
    form the same way. They differ only in whether a reason for stopping is attached.

    Attributes:
        log: Every value written, in order.
        attempted: Fields already offered to the fallback, answered or not. Separate from what was
            written, because a question the model could not answer must not be asked again on the
            next pass — that spends quota on a known-unanswerable field and brings the per-run cap
            forward for no gain (ADR-0008).
        rejected: Fallback answers the control refused, with the reason.
        passes: How many enumerate-and-fill passes have run.
    """

    log: FillLog = field(default_factory=FillLog)
    attempted: set[str] = field(default_factory=set)
    rejected: list[tuple[str, str]] = field(default_factory=list)
    passes: int = 0

    def result(
        self,
        page: Page,
        field_map: FieldMap,
        package: ApplicationPackage,
        halted: str | None = None,
    ) -> FillResult:
        """Describe the form as it now stands, whether the run finished or stopped.

        Re-resolves the page first, so every conditional field an answer revealed is counted.
        """
        final = resolve(page.fields(), field_map, package)
        written = self.log.sources()
        rejected_names = {name for name, _ in self.rejected}
        # A field the map resolved but that holds no value is the halt's own field, or one the run
        # never reached. It is not a miss the resolver can report, and leaving it out would hide
        # the very field a reviewer opens the capture to find.
        unwritten = tuple(
            Missed(
                item.field,
                MissReason.NOT_WRITTEN,
                f"resolved from {item.path}, but the value never reached the field",
            )
            for item in final.resolved
            if item.name not in written
        )
        return FillResult(
            completion=from_fill(final, written),
            log=self.log,
            outstanding=tuple(
                m for m in final.missed if m.name not in written or m.name in rejected_names
            )
            + unwritten,
            rejected_answers=tuple(self.rejected),
            passes=self.passes,
            halted=halted,
        )


def fill_form(
    page: Page,
    field_map: FieldMap,
    package: ApplicationPackage,
    *,
    answer_unmatched: Callable[[tuple[Missed, ...]], dict[str, str]] | None = None,
) -> FillResult:
    """Fill `page` from `package` using `field_map`, and halt.

    Args:
        page: The form, offline or live. The executor does not know which.
        field_map: The platform's map.
        package: The composed package supplying values.
        answer_unmatched: The bounded fallback (issue #15), given only fields no rule matched. None
            here means the deterministic path runs alone, which is how Spike A starts.

    Returns:
        A FillResult carrying the completion figure and everything that was written.

    Raises:
        HaltedRun: if a fill fails on a field the map resolved, which means the page is not what
            the map expects, or if the fallback exhausts its per-run cap. Either way the partial
            fill travels on the exception, so the run is recorded as it actually stands.
    """
    run = _Run()
    try:
        _passes(page, field_map, package, run, answer_unmatched)
    except HaltedRun as exc:
        exc.partial = run.result(page, field_map, package, halted=str(exc))
        raise

    if page.submit_activated:  # pragma: no cover - unreachable by construction, asserted anyway
        raise FormHalted("the submit control was activated, which must never happen (G3)")

    return run.result(page, field_map, package)


def _passes(
    page: Page,
    field_map: FieldMap,
    package: ApplicationPackage,
    run: _Run,
    answer_unmatched: Callable[[tuple[Missed, ...]], dict[str, str]] | None,
) -> None:
    """Enumerate and fill until a pass writes nothing, recording what happened into `run`."""
    while run.passes < MAX_PASSES:
        run.passes += 1
        resolution = resolve(page.fields(), field_map, package)
        written = run.log.sources()
        wrote_something = False

        for item in resolution.resolved:
            if item.name in written:
                continue
            try:
                _write(page, run.log, item.field, item.value, item.path)
            except (ValueError, KeyError) as exc:
                raise FormHalted(f"the page rejected a mapped value: {exc}", item.name) from exc
            wrote_something = True

        if answer_unmatched is not None:
            pending = tuple(
                m
                for m in resolution.fallback_candidates
                if m.name not in written and m.name not in run.attempted
            )
            offered = {m.name: m.field for m in pending}
            # Recorded before the answers come back, so a question the model declined is asked
            # once per run rather than once per pass.
            run.attempted.update(offered)
            for name, value in answer_unmatched(pending).items():
                if name not in offered:
                    raise FormHalted(
                        "the fallback answered a field it was not offered, which would let it "
                        "reach a field the map resolved or declined",
                        name,
                    )
                try:
                    _write(page, run.log, offered[name], value, FALLBACK_SOURCE)
                except (ValueError, KeyError) as exc:
                    # A bad answer from the non-deterministic half is localised to its own field
                    # and left unfilled, rather than halting the fill (ADR-0008). It shows up as
                    # outstanding, so a reviewer sees the question that went unanswered.
                    run.rejected.append((name, str(exc)))
                    continue
                wrote_something = True

        if not wrote_something:
            break
