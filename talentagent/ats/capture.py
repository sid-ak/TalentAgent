"""The run artifact: what a human actually reviews.

Pass 2 ends in a completed, unsubmitted form. What the reviewer opens is this, so it is the
deliverable of the phase rather than a debugging aid.

It is also the closest thing the zero-budget design has to durable observability. Actions retains
run logs and artifacts for 90 days, and every run leaving an inspectable record was one of the
reasons Actions turned out to fit this worker better than expected (ADR-0012).

Two things here are load-bearing rather than convenient. The package is frozen alongside the
capture, so a later regeneration cannot be confused with what was actually filled (Spec 11). And a
run that halts still writes everything it has, because a partial capture naming the field it stopped
on is diagnosable and a discarded run is not (Architecture 7).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from talentagent.ats.completion import Completion
from talentagent.ats.executor import FillResult
from talentagent.ats.fallback import BoundedFallback
from talentagent.ats.page import FALLBACK_SOURCE, Page
from talentagent.composer.package import ApplicationPackage

SCREENSHOT = "form.png"
"""Filenames inside a capture directory. Fixed so the review UI can find them without a manifest."""
OFFLINE_SCREENSHOT = "form.html"
RECORD = "run.json"
FROZEN_PACKAGE = "package.json"


@dataclass(frozen=True)
class FieldRecord:
    """What happened to one field, and why.

    Attributes:
        name: The control.
        outcome: One of `resolved`, `fallback`, `declined`, `unfilled`, or `rejected`.
        detail: The package path it came from, or the reason it was not filled.
        value: What was written, where anything was.
    """

    name: str
    outcome: str
    detail: str
    value: str | None = None


@dataclass
class RunCapture:
    """Everything one Pass 2 run produced.

    Attributes:
        posting_id: Which posting was filled.
        platform: Which ATS it was.
        completion: The figure the Spike A gate is measured against.
        fields: One record per field, whatever happened to it.
        fallback_answers: Every model-answered question, so the non-deterministic answers are
            visible rather than mixed in with the rest.
        halted: Why the run stopped early, if it did.
        screenshot: Where the capture image or rendered DOM was written.
    """

    posting_id: str
    platform: str
    completion: Completion
    fields: tuple[FieldRecord, ...]
    fallback_answers: tuple[dict[str, Any], ...] = ()
    halted: str | None = None
    screenshot: Path | None = None

    def to_dict(self) -> dict[str, Any]:
        """Render the capture as the JSON the review UI and the gate both read."""
        return {
            "posting_id": self.posting_id,
            "platform": self.platform,
            "captured_at": datetime.now(UTC).isoformat(),
            "halted": self.halted,
            "completion": {
                "rate": round(self.completion.rate, 4),
                "deterministic_share": round(self.completion.deterministic_share, 4),
                "by_map": self.completion.by_map,
                "by_fallback": self.completion.by_fallback,
                "unfilled": self.completion.unfilled,
                "declined": self.completion.declined,
                "not_visible": self.completion.not_visible,
            },
            "fields": [
                {"name": f.name, "outcome": f.outcome, "detail": f.detail, "value": f.value}
                for f in self.fields
            ],
            "fallback_answers": list(self.fallback_answers),
            "screenshot": self.screenshot.name if self.screenshot else None,
        }


def build_capture(
    posting_id: str,
    platform: str,
    result: FillResult,
    fallback: BoundedFallback | None = None,
    halted: str | None = None,
) -> RunCapture:
    """Assemble the per-field record from a fill result."""
    written = {value.name: value for value in result.log.values}
    fallback_names = {name for name, value in written.items() if value.source == FALLBACK_SOURCE}
    rejected = dict(result.rejected_answers)

    records: list[FieldRecord] = []
    for name, value in written.items():
        records.append(
            FieldRecord(
                name=name,
                outcome=FALLBACK_SOURCE if name in fallback_names else "resolved",
                detail=value.source,
                value=value.value,
            )
        )
    for miss in result.outstanding:
        if miss.name in written:
            continue
        outcome = (
            "rejected"
            if miss.name in rejected
            else ("declined" if miss.reason.value == "declared_unmapped" else "unfilled")
        )
        records.append(
            FieldRecord(
                name=miss.name,
                outcome=outcome,
                detail=rejected.get(miss.name, miss.detail),
            )
        )

    answers = (
        tuple(
            {
                "field": invocation.field_name,
                "question": invocation.question,
                "answer": invocation.answer,
                "confidence": invocation.confidence,
                "accepted": invocation.accepted,
            }
            for invocation in fallback.invocations
        )
        if fallback is not None
        else ()
    )
    return RunCapture(
        posting_id=posting_id,
        platform=platform,
        completion=result.completion,
        fields=tuple(records),
        fallback_answers=answers,
        halted=halted,
    )


def write_capture(
    destination: Path,
    capture: RunCapture,
    page: Page,
    package: ApplicationPackage,
    offline: bool = False,
) -> Path:
    """Write the capture, the screenshot, and the frozen package into `destination`.

    Called on success and on a halt alike. A run that stopped part-way still produces everything it
    has, because a partial capture is diagnosable and a discarded run is not.
    """
    destination.mkdir(parents=True, exist_ok=True)
    capture.screenshot = page.screenshot(
        destination / (OFFLINE_SCREENSHOT if offline else SCREENSHOT)
    )
    (destination / RECORD).write_text(json.dumps(capture.to_dict(), indent=2, sort_keys=True))
    # Frozen, not regenerated. A package written here is the one that was filled (Spec 11).
    (destination / FROZEN_PACKAGE).write_text(package.model_dump_json(indent=2))
    return destination
