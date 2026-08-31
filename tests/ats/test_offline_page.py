"""Pins the offline page backend, which is what makes the Pass 2 suite deterministic (#13)."""

from pathlib import Path

import pytest
from talentagent.ats.offline import OfflineHtmlPage, SubmitAttempted, UnknownField

from tests.conftest import ATS_FIXTURES


def test_fields_carry_the_identities_the_resolver_needs() -> None:
    """Name, label, aria, kind, options, and required all come off the DOM."""
    page = OfflineHtmlPage(ATS_FIXTURES / "ashby" / "plain.html")
    by_name = {f.name: f for f in page.fields()}
    assert by_name["_systemfield_name"].label == "Name*"
    assert by_name["_systemfield_phone"].aria == "Phone"
    assert by_name["_systemfield_phone"].label is None
    assert by_name["_systemfield_email"].required


def test_select_options_are_enumerated() -> None:
    """A select reports its permitted values, so a fill cannot invent one."""
    page = OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "custom-questions.html")
    by_name = {f.name: f for f in page.fields()}
    field = by_name["job_application[answers_attributes][1][boolean_value]"]
    assert field.options == ("1", "0")


def test_filling_a_select_with_an_unlisted_value_is_refused() -> None:
    """A value the platform would reject is refused here rather than at submit time."""
    page = OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "custom-questions.html")
    with pytest.raises(ValueError, match="is not an option"):
        page.fill("job_application[answers_attributes][1][boolean_value]", "maybe")


def test_filling_an_unknown_field_is_refused() -> None:
    """A fill targeting a field the page does not have fails loudly."""
    page = OfflineHtmlPage(ATS_FIXTURES / "lever" / "plain.html")
    with pytest.raises(UnknownField):
        page.fill("nonexistent", "x")


def test_conditional_fields_are_hidden_until_the_answer_that_reveals_them() -> None:
    """A follow-up question is not part of the form until the earlier answer is given."""
    page = OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "conditional.html")
    follow_up = "job_application[answers_attributes][1][text_value]"

    before = {f.name: f.visible for f in page.fields()}
    assert before[follow_up] is False

    page.fill("job_application[answers_attributes][0][boolean_value]", "1")
    after = {f.name: f.visible for f in page.fields()}
    assert after[follow_up] is True, "re-enumeration must see the revealed field"


def test_answering_the_other_way_leaves_the_follow_up_hidden() -> None:
    """The condition is on the value, not merely on the field having been answered."""
    page = OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "conditional.html")
    page.fill("job_application[answers_attributes][0][boolean_value]", "0")
    visible = {f.name: f.visible for f in page.fields()}
    assert visible["job_application[answers_attributes][1][text_value]"] is False


def test_uploads_attach_a_file_rather_than_a_value(tmp_path: Path) -> None:
    """A file control takes a path, and the page records what was attached."""
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF-1.4")
    page = OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "file-upload.html")
    page.upload("job_application[resume]", resume)
    assert page.uploads == {"job_application[resume]": resume}


def test_uploading_to_a_text_field_is_refused() -> None:
    """The fill primitive is chosen by the control's kind, not guessed."""
    page = OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "file-upload.html")
    with pytest.raises(ValueError, match="not a file control"):
        page.upload("job_application[email]", ATS_FIXTURES / "greenhouse" / "plain.html")


def test_the_page_cannot_be_submitted() -> None:
    """Activating the submit control raises. Submission is human-only (G3)."""
    page = OfflineHtmlPage(ATS_FIXTURES / "lever" / "plain.html")
    with pytest.raises(SubmitAttempted, match="human-only"):
        page.activate_submit()
    assert page.submit_activated is False


def test_screenshot_writes_the_filled_dom(tmp_path: Path) -> None:
    """The capture is readable and contains the values that were written."""
    page = OfflineHtmlPage(ATS_FIXTURES / "lever" / "plain.html")
    page.fill("email", "ada@example.com")
    written = page.screenshot(tmp_path / "capture.html")
    assert "ada@example.com" in written.read_text()
