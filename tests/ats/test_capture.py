"""Pins the run artifact, including what a halted run still produces (issue #16)."""

import json
from pathlib import Path

import pytest
from talentagent.ats.capture import FROZEN_PACKAGE, RECORD, build_capture, write_capture
from talentagent.ats.completion import ZERO
from talentagent.ats.executor import FillResult, FormHalted, fill_form
from talentagent.ats.fallback import BoundedFallback
from talentagent.ats.fieldmap import load_map
from talentagent.ats.offline import OfflineHtmlPage
from talentagent.ats.package import ApplicationPackage
from talentagent.models.client import ModelCall, ModelClient

from tests.ats.conftest import ATS_FIXTURES


def _answering_client(golden: Path) -> ModelClient:
    """A client that answers every custom question confidently, choosing a legal option."""

    def transport(call: ModelCall) -> dict[str, object]:
        options = call.data["options"]
        assert isinstance(options, list)
        return {"answer": options[0] if options else "An answer.", "confidence": 0.9}

    return ModelClient(golden_root=golden, transport=transport, record=True)


def test_a_successful_run_writes_a_capture_a_record_and_the_frozen_package(
    package: ApplicationPackage, tmp_path: Path
) -> None:
    """The three artifacts a reviewer needs, all present."""
    page = OfflineHtmlPage(ATS_FIXTURES / "lever" / "plain.html")
    result = fill_form(page, load_map("lever"), package)
    capture = build_capture("job_9a2", "lever", result)
    written = write_capture(tmp_path / "run", capture, page, package, offline=True)

    assert (written / RECORD).exists()
    assert (written / FROZEN_PACKAGE).exists()
    assert capture.screenshot is not None
    assert capture.screenshot.exists()


def test_the_frozen_package_matches_the_one_filled(
    package: ApplicationPackage, tmp_path: Path
) -> None:
    """A later regeneration cannot be confused with what was actually filled (Spec 11)."""
    page = OfflineHtmlPage(ATS_FIXTURES / "lever" / "plain.html")
    result = fill_form(page, load_map("lever"), package)
    written = write_capture(
        tmp_path / "run", build_capture("job_9a2", "lever", result), page, package, offline=True
    )
    frozen = json.loads((written / FROZEN_PACKAGE).read_text())
    assert frozen == json.loads(package.model_dump_json())


def test_the_record_carries_one_entry_per_field_with_its_outcome(
    package: ApplicationPackage, tmp_path: Path
) -> None:
    """Nothing is unaccounted for: every field is resolved, fallback, declined, or unfilled."""
    page = OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "custom-questions.html")
    fallback = BoundedFallback(client=_answering_client(tmp_path), package=package)
    result = fill_form(page, load_map("greenhouse"), package, answer_unmatched=fallback)
    capture = build_capture("job_9a2", "greenhouse", result, fallback)

    outcomes = {f.name: f.outcome for f in capture.fields}
    assert len(outcomes) == len(page.fields())
    assert set(outcomes.values()) <= {"resolved", "fallback", "declined", "unfilled", "rejected"}
    assert outcomes["job_application[email]"] == "resolved"
    assert outcomes["job_application[answers_attributes][0][text_value]"] == "fallback"
    assert outcomes["job_application[demographic][gender]"] == "declined"


def test_model_answered_fields_are_listed_separately_with_their_confidence(
    package: ApplicationPackage, tmp_path: Path
) -> None:
    """A reviewer sees exactly which answers were not deterministic, and how sure the model was."""
    page = OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "custom-questions.html")
    fallback = BoundedFallback(client=_answering_client(tmp_path), package=package)
    result = fill_form(page, load_map("greenhouse"), package, answer_unmatched=fallback)
    capture = build_capture("job_9a2", "greenhouse", result, fallback)

    assert len(capture.fallback_answers) == 4
    assert all("confidence" in answer for answer in capture.fallback_answers)
    assert all(answer["accepted"] for answer in capture.fallback_answers)


def test_the_completion_figure_is_written_into_the_record(
    package: ApplicationPackage, tmp_path: Path
) -> None:
    """The gate reads its number from the artifact rather than recomputing it."""
    page = OfflineHtmlPage(ATS_FIXTURES / "ashby" / "plain.html")
    result = fill_form(page, load_map("ashby"), package)
    written = write_capture(
        tmp_path / "run", build_capture("job_9a2", "ashby", result), page, package, offline=True
    )
    record = json.loads((written / RECORD).read_text())
    assert record["completion"]["rate"] == 1.0
    assert record["halted"] is None


def test_a_halted_run_still_produces_a_capture_naming_the_field(
    package: ApplicationPackage, tmp_path: Path
) -> None:
    """A DOM change loses the run, not the evidence of what went wrong (Architecture 7)."""
    source = ATS_FIXTURES / "greenhouse" / "plain.html"
    changed = tmp_path / "plain.html"
    changed.write_text(
        source.read_text().replace(
            '<input type="email" id="email" name="job_application[email]" required>',
            '<select id="email" name="job_application[email]">'
            '<option value="a@example.com">a</option></select>',
        )
    )
    page = OfflineHtmlPage(changed)
    with pytest.raises(FormHalted) as caught:
        fill_form(page, load_map("greenhouse"), package)

    partial = build_capture("job_9a2", "greenhouse", _empty_result(), halted=str(caught.value))
    written = write_capture(tmp_path / "run", partial, page, package, offline=True)
    record = json.loads((written / RECORD).read_text())
    assert "job_application[email]" in record["halted"]
    assert (written / FROZEN_PACKAGE).exists()
    assert "Ada" in (written / "form.html").read_text(), "the partial fill survives"


def _empty_result() -> FillResult:
    """Return a fill result carrying nothing, as a halt before completion would leave."""
    return FillResult(completion=ZERO)
