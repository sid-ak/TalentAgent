"""Run every fixture on every platform and report the Spike A completion table.

Invoked by CI and by a human running `uv run python -m talentagent.jobs.spike_a_gate`. Reproducible
by construction: the fixtures are offline, the model responses are replayed, and the figure comes
out of the same captures a reviewer reads.
"""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

from talentagent.ats.capture import build_capture, write_capture
from talentagent.ats.executor import fill_form
from talentagent.ats.fallback import BoundedFallback
from talentagent.ats.fieldmap import load_map
from talentagent.ats.gate import THRESHOLD, GateReport, report_from_captures
from talentagent.ats.halt import HaltedRun
from talentagent.ats.offline import OfflineHtmlPage
from talentagent.ats.package import ApplicationPackage, Identity, Links, Materials
from talentagent.models.client import ModelCall, ModelClient

PLATFORMS = ("greenhouse", "lever", "ashby")
FIXTURE_ROOT = Path("tests/fixtures/ats")


def reference_package(work: Path) -> ApplicationPackage:
    """Build the package the gate fills every fixture from.

    Deliberately one package across all three platforms: the completion figure should measure the
    maps, not the luck of a package tailored per platform.
    """
    resume = work / "resume.pdf"
    resume.write_bytes(b"%PDF-1.4 resume")
    cover = work / "cover.pdf"
    cover.write_bytes(b"%PDF-1.4 cover")
    return ApplicationPackage(
        posting_id="job_gate",
        identity=Identity(
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            phone="+44 20 7946 0000",
            location="London",
            current_company="Analytical Engines",
        ),
        links=Links(
            linkedin="https://www.linkedin.com/in/example",
            github="https://github.com/example",
        ),
        materials=Materials(
            resume=resume, cover_letter=cover, cover_letter_text="A short cover letter."
        ),
    )


def _gate_client(golden: Path) -> ModelClient:
    """A client answering custom questions from the package, recording as it goes."""

    def transport(call: ModelCall) -> dict[str, object]:
        options = call.data["options"]
        assert isinstance(options, list)
        return {
            "answer": options[0] if options else "Answered from the composed package.",
            "confidence": 0.9,
        }

    return ModelClient(golden_root=golden, transport=transport, record=True)


def run_all(work: Path, fixture_root: Path = FIXTURE_ROOT) -> GateReport:
    """Fill every fixture on every platform and return the completion table."""
    work.mkdir(parents=True, exist_ok=True)
    package = reference_package(work)
    artifacts = work / "artifacts"
    client = _gate_client(work / "golden")

    for platform in PLATFORMS:
        for fixture in sorted((fixture_root / platform).glob("*.html")):
            page = OfflineHtmlPage(fixture)
            fallback = BoundedFallback(client=client, package=package)
            halted: str | None = None
            try:
                result = fill_form(page, load_map(platform), package, answer_unmatched=fallback)
            except HaltedRun as exc:  # pragma: no cover - fixtures are not expected to halt
                # Measured from the partial fill rather than from an empty figure: a fixture that
                # halts should pull its platform's completion down, not read as a clean 100%.
                halted, result = str(exc), exc.partial_fill()
            capture = build_capture(
                f"{platform}/{fixture.stem}", platform, result, fallback, halted
            )
            write_capture(artifacts / platform / fixture.stem, capture, page, package, offline=True)
    return report_from_captures(artifacts)


def main(argv: list[str] | None = None) -> int:
    """Print the completion table and fail if any platform is below the threshold."""
    parser = argparse.ArgumentParser(description="Measure Spike A completion across fixtures.")
    parser.add_argument("--work", type=Path, default=Path(".gate"))
    args = parser.parse_args(argv)
    args.work.mkdir(parents=True, exist_ok=True)

    report = run_all(args.work)
    print(report.to_markdown())
    if not report.passed:
        print(
            f"\nBelow the {THRESHOLD:.0%} threshold: {', '.join(report.failing)}. "
            f"A platform that cannot reach it is dropped rather than the criterion lowered "
            f"(ADR-0011).",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":  # pragma: no cover - entry point
    raise SystemExit(main())
