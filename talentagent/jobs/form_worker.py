"""The form worker: fetch a posting, fill its form from the package, capture, and halt.

Runs on GitHub Actions rather than beside the state layer, because Actions is where Chromium and
unmetered minutes are (Architecture 2.1).

The entry point is a `main()` a workflow calls, and the work is a library function the tests call
with a fixture page. That split is deliberate: the worker's behaviour — including its failure
handling — is exercised offline rather than only in a live run.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path

from talentagent.ats.capture import RunCapture, build_capture, write_capture
from talentagent.ats.executor import FillResult, FormHalted, fill_form
from talentagent.ats.fallback import BoundedFallback
from talentagent.ats.fieldmap import FieldMap, load_map
from talentagent.ats.halt import HaltedRun
from talentagent.ats.page import Page
from talentagent.ats.platforms import UnsupportedPlatform, platform_for
from talentagent.composer.package import ApplicationPackage
from talentagent.models.client import GoldenResponseMissing, ModelClient, QuotaExhausted
from talentagent.net.fetch import Fetcher
from talentagent.state.packages import PackageStore

__all__ = ["UnsupportedPlatform", "WorkerOutcome", "main", "platform_for", "run"]
"""Re-exported from `talentagent.ats.platforms`, which the live page backend also reads."""

_NO_TRANSPORT = (
    "No recorded response covered a custom question and no live model transport is configured, "
    "so custom questions were left unanswered. The deterministic fill completed; the first live "
    "run is issue #18."
)
"""Why a run degrades when the model cannot be reached at all. The replay layer answers every
question the fixtures cover, and Phase 5 wires the live transport behind it; until then a genuinely
novel question degrades the run rather than crashing it (Architecture 7).
"""


@dataclass
class WorkerOutcome:
    """What one worker run produced.

    Attributes:
        capture: The run artifact.
        artifact_dir: Where it was written.
        degraded: Set when the run finished without the model — the daily quota was exhausted, or
            no transport was configured to answer a question the recordings do not cover.
    """

    capture: RunCapture
    artifact_dir: Path
    degraded: str | None = None


def run(
    *,
    application_id: str,
    posting_url: str,
    page: Page,
    store: PackageStore,
    client: ModelClient,
    artifacts: Path,
    offline: bool = False,
) -> WorkerOutcome:
    """Fill one form and write its artifact, whatever happens.

    Every failure path here degrades or halts rather than escalating (Architecture 7):

    - A DOM change halts with a partial capture naming the field.
    - An exhausted daily quota finishes the deterministic fill without the fallback and reports
      itself as degraded, rather than failing silently or spinning.
    - A fallback cap halts, because that many unmapped fields is a map problem.
    - A question with no recorded response and no live transport behind it degrades the same way
      the quota does, so the run still produces an artifact (see `_NO_TRANSPORT`).
    """
    platform = platform_for(posting_url)
    package = store.load(application_id)
    field_map = load_map(platform)
    fallback = BoundedFallback(client=client, package=package)

    halted: str | None = None
    degraded: str | None = None
    try:
        result = fill_form(page, field_map, package, answer_unmatched=fallback)
    except QuotaExhausted:
        degraded = (
            "The Gemini daily quota was exhausted, so custom questions were left unanswered. "
            "The deterministic fill completed; re-run tomorrow to answer the rest."
        )
        result = _deterministic_only(page, field_map, package)
    except GoldenResponseMissing:
        degraded = _NO_TRANSPORT
        result = _deterministic_only(page, field_map, package)
    except HaltedRun as exc:
        halted = str(exc)
        # The partial fill travels on the halt, so the capture reports the form as it actually
        # stands. An empty figure here would read as a form with nothing left to fill.
        result = exc.partial_fill()

    capture = build_capture(package.posting_id, platform, result, fallback, halted=halted)
    artifact_dir = write_capture(
        artifacts / application_id, capture, page, package, offline=offline
    )
    store.record_capture(application_id, str(artifact_dir), capture.completion.rate)
    return WorkerOutcome(capture=capture, artifact_dir=artifact_dir, degraded=degraded)


def _deterministic_only(page: Page, field_map: FieldMap, package: ApplicationPackage) -> FillResult:
    """Re-run the fill with no fallback, for the degraded paths."""
    return fill_form(page, field_map, package)


def main(argv: list[str] | None = None) -> int:
    """Entry point the workflow calls."""
    parser = argparse.ArgumentParser(description="Fill an ATS form from a composed package.")
    parser.add_argument("--application-id", required=True)
    parser.add_argument("--posting-url", required=True)
    parser.add_argument("--artifacts", type=Path, default=Path("artifacts"))
    parser.add_argument("--packages", type=Path, default=Path("packages"))
    args = parser.parse_args(argv)

    from talentagent.ats.chromium import ChromiumPage
    from talentagent.state.packages import LocalPackageStore

    # Checked before the browser starts, so an out-of-scope host costs nothing (G5).
    Fetcher().check(args.posting_url)
    platform_for(args.posting_url)

    with ChromiumPage(args.posting_url) as page:
        outcome = run(
            application_id=args.application_id,
            posting_url=args.posting_url,
            page=page,
            store=LocalPackageStore(args.packages),
            client=ModelClient(),
            artifacts=args.artifacts,
        )
        if not page.submit_control_is_untouched():  # pragma: no cover - asserted, never expected
            raise FormHalted("the page navigated away, which suggests a submission (G3)")

    print(f"completion={outcome.capture.completion.rate:.3f} artifact={outcome.artifact_dir}")
    if outcome.degraded:
        print(f"degraded: {outcome.degraded}", file=sys.stderr)
    return 1 if outcome.capture.halted else 0


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
