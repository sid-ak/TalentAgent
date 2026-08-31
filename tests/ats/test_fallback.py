"""Pins the four bounds on the model fallback (issue #15)."""

import json
from pathlib import Path

import pytest
from talentagent.ats.executor import fill_form
from talentagent.ats.fallback import (
    SCHEMA,
    BoundedFallback,
    FallbackCapExceeded,
    FallbackReachedMappedField,
)
from talentagent.ats.fieldmap import MissReason, load_map
from talentagent.ats.offline import OfflineHtmlPage
from talentagent.ats.package import ApplicationPackage, ScreeningAnswer
from talentagent.ats.page import FormField
from talentagent.ats.resolver import Missed
from talentagent.models.client import ModelCall, ModelClient, Tier

from tests.ats.conftest import ATS_FIXTURES


def _client(golden: Path, answers: dict[str, tuple[str, float]]) -> ModelClient:
    """Return a client whose recorded responses answer by question text."""

    def transport(call: ModelCall) -> dict[str, object]:
        answer, confidence = answers.get(str(call.data["question"]), ("", 0.0))
        return {"answer": answer, "confidence": confidence}

    return ModelClient(golden_root=golden, transport=transport, record=True)


def _miss(name: str, label: str, options: tuple[str, ...] = ()) -> Missed:
    """Build an unmatched field, as the resolver would report one."""
    return Missed(
        FormField(name=name, kind="text", label=label, options=options), MissReason.NO_RULE
    )


def test_the_fallback_cannot_be_reached_for_a_mapped_field(
    package: ApplicationPackage, tmp_path: Path
) -> None:
    """Offering a declined field raises rather than being quietly answered."""
    fallback = BoundedFallback(client=_client(tmp_path, {}), package=package)
    declined = Missed(
        FormField(name="eeo", kind="select", label="Gender"), MissReason.DECLARED_UNMAPPED
    )
    with pytest.raises(FallbackReachedMappedField, match="eeo"):
        fallback((declined,))


def test_an_answer_is_traceable_to_the_package_field_it_came_from(
    package: ApplicationPackage, tmp_path: Path
) -> None:
    """The answer comes from the composed package, and the invocation records the question."""
    package.screening_answers.append(
        ScreeningAnswer(question="Years of Python", value="4", credits=["acc_7f21"])
    )
    fallback = BoundedFallback(
        client=_client(tmp_path, {"How many years of Python?": ("4", 0.92)}), package=package
    )
    answers = fallback((_miss("q_0", "How many years of Python?"),))
    assert answers == {"q_0": "4"}
    assert fallback.accepted[0].question == "How many years of Python?"
    assert fallback.accepted[0].confidence == pytest.approx(0.92)


def test_a_low_confidence_answer_is_left_empty_and_recorded(
    package: ApplicationPackage, tmp_path: Path
) -> None:
    """Below the threshold the field stays empty rather than being filled with a guess."""
    fallback = BoundedFallback(
        client=_client(tmp_path, {"Do you have a security clearance?": ("Yes", 0.3)}),
        package=package,
    )
    assert fallback((_miss("q_1", "Do you have a security clearance?"),)) == {}
    assert fallback.rejected[0].field_name == "q_1"
    assert fallback.rejected[0].answer == "Yes", "the rejected answer is retained for review"


def test_an_answer_outside_the_controls_options_is_not_written(
    package: ApplicationPackage, tmp_path: Path
) -> None:
    """A confident answer the control would refuse is treated as low confidence, not written."""
    fallback = BoundedFallback(
        client=_client(tmp_path, {"Sponsorship required?": ("Perhaps", 0.99)}), package=package
    )
    assert fallback((_miss("q_2", "Sponsorship required?", options=("Yes", "No")),)) == {}
    assert not fallback.accepted


def test_the_per_run_cap_halts_rather_than_draining_the_quota(
    package: ApplicationPackage, tmp_path: Path
) -> None:
    """More unmapped fields than the cap means a map problem, so the run halts visibly."""
    fallback = BoundedFallback(client=_client(tmp_path, {}), package=package, max_invocations=2)
    with pytest.raises(FallbackCapExceeded, match="cap of 2"):
        fallback(tuple(_miss(f"q_{i}", f"Question {i}?") for i in range(3)))


def test_the_raw_page_is_never_passed_as_input(package: ApplicationPackage, tmp_path: Path) -> None:
    """The model sees the field's own label and the package, never the page (G7)."""
    seen: list[ModelCall] = []

    def transport(call: ModelCall) -> dict[str, object]:
        seen.append(call)
        return {"answer": "yes", "confidence": 0.9}

    client = ModelClient(golden_root=tmp_path, transport=transport, record=True)
    BoundedFallback(client=client, package=package)((_miss("q_0", "Remote experience?"),))

    assert set(seen[0].data) == {"question", "options", "kind", "package"}
    assert "html" not in json.dumps(seen[0].data).lower()


def test_the_fallback_uses_tier_two_and_records_a_golden_fixture(
    package: ApplicationPackage, tmp_path: Path
) -> None:
    """Composition-grade judgement is tier 2, and every call is replayable afterwards."""
    fallback = BoundedFallback(
        client=_client(tmp_path, {"Why this role?": ("Because of the work.", 0.8)}),
        package=package,
    )
    fallback((_miss("q_0", "Why this role?"),))
    recorded = list((tmp_path / Tier.TWO.value).glob("*.json"))
    assert len(recorded) == 1
    assert json.loads(recorded[0].read_text())["schema"] == SCHEMA


def test_a_custom_question_form_completes_end_to_end(
    package: ApplicationPackage, tmp_path: Path
) -> None:
    """Map plus fallback fills every fillable field on a real fixture, with no network."""
    page = OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "custom-questions.html")

    def transport(call: ModelCall) -> dict[str, object]:
        options = call.data["options"]
        assert isinstance(options, list)
        return {"answer": options[0] if options else "An answer.", "confidence": 0.9}

    client = ModelClient(golden_root=tmp_path, transport=transport, record=True)
    fallback = BoundedFallback(client=client, package=package)
    result = fill_form(page, load_map("greenhouse"), package, answer_unmatched=fallback)

    assert result.completion.rate == 1.0
    assert result.completion.by_fallback == 4, "the four custom questions came from the fallback"
    assert result.completion.declined == 4, "the demographic questions stayed declined"
    assert not any("demographic" in name for name in page.values)
