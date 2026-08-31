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

from talentagent.ats.completion import Completion, from_resolution
from talentagent.ats.fieldmap import FieldMap
from talentagent.ats.package import ApplicationPackage
from talentagent.ats.page import FillLog, FormField, Page
from talentagent.ats.resolver import Missed, resolve

#: How many enumerate-and-fill passes to make before concluding the form has stopped changing.
#: Three is comfortably above the deepest conditional chain the target platforms produce, and a cap
#: rather than a while-loop so a page that rewrites itself cannot spin.
MAX_PASSES = 4


class FormHalted(RuntimeError):
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
        FormHalted: if a fill fails on a field the map resolved, which means the page is not what
            the map expects.
    """
    log = FillLog()
    filled: set[str] = set()
    rejected: list[tuple[str, str]] = []
    passes = 0
    fallback_count = 0

    while passes < MAX_PASSES:
        passes += 1
        resolution = resolve(page.fields(), field_map, package)
        wrote_something = False

        for item in resolution.resolved:
            if item.name in filled:
                continue
            try:
                _write(page, log, item.field, item.value, item.path)
            except (ValueError, KeyError) as exc:
                raise FormHalted(f"the page rejected a mapped value: {exc}", item.name) from exc
            filled.add(item.name)
            wrote_something = True

        if answer_unmatched is not None:
            pending = tuple(m for m in resolution.fallback_candidates if m.name not in filled)
            offered = {m.name: m.field for m in pending}
            for name, value in answer_unmatched(pending).items():
                if name not in offered:
                    raise FormHalted(
                        "the fallback answered a field it was not offered, which would let it "
                        "reach a field the map resolved or declined",
                        name,
                    )
                try:
                    _write(page, log, offered[name], value, "fallback")
                except (ValueError, KeyError) as exc:
                    # A bad answer from the non-deterministic half is localised to its own field
                    # and left unfilled, rather than halting the fill (ADR-0008). It shows up as
                    # outstanding, so a reviewer sees the question that went unanswered.
                    rejected.append((name, str(exc)))
                    filled.add(name)
                    continue
                filled.add(name)
                fallback_count += 1
                wrote_something = True

        if not wrote_something:
            break

    # Re-resolve once more so the reported figure describes the form as it finally stands, with
    # every conditional field that was revealed now counted.
    final = resolve(page.fields(), field_map, package)
    completion = from_resolution(final)
    completion = Completion(
        by_map=completion.by_map,
        by_fallback=fallback_count,
        unfilled=max(completion.unfilled - fallback_count, 0),
        declined=completion.declined,
        not_visible=completion.not_visible,
    )

    if page.submit_activated:  # pragma: no cover - unreachable by construction, asserted anyway
        raise FormHalted("the submit control was activated, which must never happen (G3)")

    rejected_names = {name for name, _ in rejected}
    return FillResult(
        completion=completion,
        log=log,
        outstanding=tuple(
            m for m in final.missed if m.name not in filled or m.name in rejected_names
        ),
        rejected_answers=tuple(rejected),
        passes=passes,
    )
