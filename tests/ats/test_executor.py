"""Pins Pass 2's fill loop, its halting behaviour, and its inability to submit (issue #14)."""

from pathlib import Path

import pytest
from talentagent.ats.executor import FormHalted, fill_form
from talentagent.ats.fieldmap import load_map
from talentagent.ats.offline import OfflineHtmlPage
from talentagent.ats.package import ApplicationPackage
from talentagent.ats.resolver import Missed

from tests.conftest import ATS_FIXTURES

PLATFORMS = ("greenhouse", "lever", "ashby")
FIXTURES = ("plain.html", "file-upload.html", "custom-questions.html", "conditional.html")


@pytest.mark.parametrize("platform", PLATFORMS)
def test_a_plain_form_fills_completely_with_the_network_disabled(
    platform: str, package: ApplicationPackage
) -> None:
    """The deterministic path alone covers every standard field, offline."""
    page = OfflineHtmlPage(ATS_FIXTURES / platform / "plain.html")
    result = fill_form(page, load_map(platform), package)
    assert result.completion.rate == 1.0
    assert not result.outstanding


@pytest.mark.parametrize("platform", PLATFORMS)
def test_uploads_are_attached_rather_than_typed(platform: str, package: ApplicationPackage) -> None:
    """A file control takes the package's rendered document, chosen by the control's kind."""
    page = OfflineHtmlPage(ATS_FIXTURES / platform / "file-upload.html")
    fill_form(page, load_map(platform), package)
    assert page.uploads, f"{platform} attached nothing"
    assert all(path.exists() for path in page.uploads.values())


def test_conditional_fields_are_filled_after_the_answer_reveals_them(
    package: ApplicationPackage,
) -> None:
    """The executor re-enumerates, so a field revealed by an earlier answer is not missed."""
    page = OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "conditional.html")
    revealed = "job_application[answers_attributes][1][text_value]"

    def answer(pending: tuple[Missed, ...]) -> dict[str, str]:
        """Answer the sponsorship question yes on the first pass, then the follow-up."""
        names = {m.name for m in pending}
        if "job_application[answers_attributes][0][boolean_value]" in names:
            return {"job_application[answers_attributes][0][boolean_value]": "1"}
        if revealed in names:
            return {revealed: "H-1B"}
        return {}

    result = fill_form(page, load_map("greenhouse"), package, answer_unmatched=answer)
    assert page.values[revealed] == "H-1B"
    assert result.passes >= 2, "a revealed field requires a second pass"


def test_the_loop_stops_when_a_pass_reveals_nothing_new(package: ApplicationPackage) -> None:
    """A form with no conditionals settles in a single pass rather than looping to the cap."""
    page = OfflineHtmlPage(ATS_FIXTURES / "lever" / "plain.html")
    assert fill_form(page, load_map("lever"), package).passes == 2


def test_a_dom_change_on_a_mapped_field_halts_with_a_partial_fill(
    package: ApplicationPackage, changed_form: Path
) -> None:
    """When the page rejects a value the map resolved, the run stops rather than guessing on.

    The halt carries the fill as it stood, so the run is recorded at the completion it actually
    reached: an empty figure would read as a form with nothing left to fill.
    """
    page = OfflineHtmlPage(changed_form)
    with pytest.raises(FormHalted) as caught:
        fill_form(page, load_map("greenhouse"), package)
    assert caught.value.field_name == "job_application[email]"
    assert page.values, "a partial fill survives the halt"

    partial = caught.value.partial_fill()
    assert partial.halted is not None
    assert partial.completion.rate < 1.0, "a run that stopped is not a complete one"
    assert partial.completion.unfilled >= 1
    assert partial.log.values, "what was filled before the halt is kept"
    assert "job_application[email]" in {m.name for m in partial.outstanding}


@pytest.mark.parametrize("platform", PLATFORMS)
@pytest.mark.parametrize("fixture", FIXTURES)
def test_no_run_ever_submits(platform: str, fixture: str, package: ApplicationPackage) -> None:
    """Across every fixture on every platform, the submit control is untouched (G3)."""
    page = OfflineHtmlPage(ATS_FIXTURES / platform / fixture)
    result = fill_form(page, load_map(platform), package)
    assert page.submit_activated is False
    assert result.submitted is False


@pytest.mark.parametrize("platform", PLATFORMS)
def test_declined_fields_are_never_offered_to_the_fallback(
    platform: str, package: ApplicationPackage
) -> None:
    """A declined field stays empty even when the fallback answers everything it is given."""
    page = OfflineHtmlPage(ATS_FIXTURES / platform / "custom-questions.html")
    offered: list[str] = []

    def answer_everything(pending: tuple[Missed, ...]) -> dict[str, str]:
        """Answer every offered field, choosing a legal option where the control constrains it."""
        offered.extend(m.name for m in pending)
        return {m.name: (m.field.options[0] if m.field.options else "answer") for m in pending}

    fill_form(page, load_map(platform), package, answer_unmatched=answer_everything)
    assert not any("demographic" in name for name in page.values)
    assert not any("demographic" in name for name in offered)


def test_a_fallback_answer_the_control_rejects_is_localised(
    package: ApplicationPackage,
) -> None:
    """A bad answer from the non-deterministic half loses one field, not the whole fill."""
    page = OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "custom-questions.html")
    constrained = "job_application[answers_attributes][1][boolean_value]"

    def answer(pending: tuple[Missed, ...]) -> dict[str, str]:
        """Answer every question legally except the one deliberately given a bad value."""
        answers = {}
        for miss in pending:
            if miss.name == constrained:
                answers[miss.name] = "not an option"
            else:
                answers[miss.name] = miss.field.options[0] if miss.field.options else "answered"
        return answers

    result = fill_form(page, load_map("greenhouse"), package, answer_unmatched=answer)
    assert dict(result.rejected_answers).keys() == {constrained}
    assert constrained not in page.values
    assert page.values["job_application[answers_attributes][0][text_value]"] == "answered"


def test_a_fallback_reaching_beyond_what_it_was_offered_halts(
    package: ApplicationPackage,
) -> None:
    """The fallback cannot answer a field the map resolved or declined, even by name."""
    page = OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "custom-questions.html")

    def overreach(_pending: tuple[Missed, ...]) -> dict[str, str]:
        """Try to answer a field the map already resolved."""
        return {"job_application[email]": "attacker@example.com"}

    with pytest.raises(FormHalted, match="not offered"):
        fill_form(page, load_map("greenhouse"), package, answer_unmatched=overreach)


def test_a_question_the_fallback_cannot_answer_is_asked_once_per_run(
    package: ApplicationPackage,
) -> None:
    """A rejected answer is not re-offered on the next pass, which would spend quota twice."""
    page = OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "conditional.html")
    offered: list[str] = []

    def decline_everything(pending: tuple[Missed, ...]) -> dict[str, str]:
        """Take every question and answer none, as a low-confidence run would."""
        offered.extend(m.name for m in pending)
        return {}

    result = fill_form(page, load_map("greenhouse"), package, answer_unmatched=decline_everything)
    assert result.passes >= 2, "the map writes on the first pass, so the loop runs again"
    assert len(offered) == len(set(offered)), f"a question was asked more than once: {offered}"


def test_a_halt_raised_outside_a_fill_carries_nothing_and_says_so() -> None:
    """The post-run navigation check halts with no fill behind it, and must not invent a figure."""
    with pytest.raises(RuntimeError, match="no partial fill"):
        FormHalted("the page navigated away, which suggests a submission (G3)").partial_fill()
