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
from urllib.parse import urlparse

from talentagent.ats.capture import RunCapture, build_capture, write_capture
from talentagent.ats.completion import ZERO
from talentagent.ats.executor import FillResult, FormHalted, fill_form
from talentagent.ats.fallback import BoundedFallback, FallbackCapExceeded
from talentagent.ats.fieldmap import load_map
from talentagent.ats.package import ApplicationPackage
from talentagent.ats.page import Page
from talentagent.models.client import ModelClient, QuotaExhausted
from talentagent.net.fetch import Fetcher
from talentagent.state.packages import PackageStore

PLATFORM_BY_HOST = {
    "boards.greenhouse.io": "greenhouse",
    "job-boards.greenhouse.io": "greenhouse",
    "jobs.lever.co": "lever",
    "jobs.ashbyhq.com": "ashby",
}
"""Maps a posting host to the platform whose field map applies to it."""


class UnsupportedPlatform(ValueError):
    """Raised when a posting URL is not one of the three targeted platforms."""

    def __init__(self, host: str) -> None:
        """Name the host that has no field map."""
        self.host = host
        super().__init__(
            f"No field map for {host!r}. The build targets Greenhouse, Lever, and Ashby "
            f"(ADR-0010); a platform below 90% on fixtures is dropped rather than half-supported."
        )


@dataclass
class WorkerOutcome:
    """What one worker run produced.

    Attributes:
        capture: The run artifact.
        artifact_dir: Where it was written.
        degraded: Set when the run finished without the model, because the quota was exhausted.
    """

    capture: RunCapture
    artifact_dir: Path
    degraded: str | None = None


def platform_for(url: str) -> str:
    """Return the platform a posting URL belongs to.

    Raises:
        UnsupportedPlatform: if there is no map for its host.
    """
    host = urlparse(url).hostname or ""
    if host not in PLATFORM_BY_HOST:
        raise UnsupportedPlatform(host)
    return PLATFORM_BY_HOST[host]


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
    except (FormHalted, FallbackCapExceeded) as exc:
        halted = str(exc)
        result = FillResult(completion=ZERO)

    capture = build_capture(package.posting_id, platform, result, fallback, halted=halted)
    artifact_dir = write_capture(
        artifacts / application_id, capture, page, package, offline=offline
    )
    store.record_capture(application_id, str(artifact_dir), capture.completion.rate)
    return WorkerOutcome(capture=capture, artifact_dir=artifact_dir, degraded=degraded)


def _deterministic_only(page: Page, field_map: object, package: ApplicationPackage) -> FillResult:
    """Re-run the fill with no fallback, for the degraded path."""
    from talentagent.ats.fieldmap import FieldMap

    assert isinstance(field_map, FieldMap)
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
