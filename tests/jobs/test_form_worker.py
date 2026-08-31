"""Pins the form worker's routing, failure handling, and secret hygiene (issue #17)."""

import json
from pathlib import Path

import pytest
import yaml
from talentagent.ats.offline import OfflineHtmlPage
from talentagent.ats.package import ApplicationPackage
from talentagent.jobs.form_worker import UnsupportedPlatform, platform_for, run
from talentagent.models.client import ModelCall, ModelClient, QuotaExhausted, Tier
from talentagent.net.fetch import AllowlistViolation, Fetcher
from talentagent.state.packages import LocalPackageStore

from tests.conftest import ATS_FIXTURES

WORKFLOW = Path(".github/workflows/form-worker.yml")


@pytest.fixture
def store(tmp_path: Path, package: ApplicationPackage) -> LocalPackageStore:
    """A package store holding one composed package for `app_1`."""
    store = LocalPackageStore(tmp_path / "packages")
    store.save("app_1", package)
    return store


def _client(tmp_path: Path, answer: str = "An answer.", confidence: float = 0.9) -> ModelClient:
    """A recording client that answers every custom question."""

    def transport(call: ModelCall) -> dict[str, object]:
        options = call.data["options"]
        assert isinstance(options, list)
        return {
            "answer": options[0] if options else answer,
            "confidence": confidence,
        }

    return ModelClient(golden_root=tmp_path / "golden", transport=transport, record=True)


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://boards.greenhouse.io/acme/jobs/1", "greenhouse"),
        ("https://jobs.lever.co/acme/abc", "lever"),
        ("https://jobs.ashbyhq.com/acme/xyz", "ashby"),
    ],
)
def test_the_platform_is_chosen_from_the_posting_host(url: str, expected: str) -> None:
    """Each targeted platform routes to its own field map."""
    assert platform_for(url) == expected


def test_an_untargeted_platform_is_refused_before_the_browser_starts() -> None:
    """A host with no map costs nothing, and the refusal explains the scope decision."""
    with pytest.raises(UnsupportedPlatform, match="ADR-0010"):
        platform_for("https://www.linkedin.com/jobs/view/1")


def test_an_unlisted_host_is_refused_by_the_allowlist() -> None:
    """The worker checks G5 before doing any work."""
    with pytest.raises(AllowlistViolation):
        Fetcher().check("https://example.com/jobs/1")


def test_a_run_writes_a_package_a_capture_and_a_completion_figure(
    store: LocalPackageStore, package: ApplicationPackage, tmp_path: Path
) -> None:
    """A dispatch with a fixture posting completes and leaves everything a reviewer needs."""
    page = OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "custom-questions.html")
    outcome = run(
        application_id="app_1",
        posting_url="https://boards.greenhouse.io/acme/jobs/1",
        page=page,
        store=store,
        client=_client(tmp_path),
        artifacts=tmp_path / "artifacts",
        offline=True,
    )
    assert outcome.capture.completion.rate == 1.0
    assert (outcome.artifact_dir / "run.json").exists()
    assert (outcome.artifact_dir / "package.json").exists()

    pointer = json.loads((store.root / "app_1.capture.json").read_text())
    assert pointer["completion"] == 1.0


def test_an_exhausted_quota_degrades_rather_than_failing_silently(
    store: LocalPackageStore, tmp_path: Path
) -> None:
    """The deterministic fill still completes, and the run says what was left undone."""

    def transport(_call: ModelCall) -> dict[str, object]:
        raise QuotaExhausted(Tier.TWO)

    client = ModelClient(golden_root=tmp_path / "golden", transport=transport, record=True)
    page = OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "custom-questions.html")
    outcome = run(
        application_id="app_1",
        posting_url="https://boards.greenhouse.io/acme/jobs/1",
        page=page,
        store=store,
        client=client,
        artifacts=tmp_path / "artifacts",
        offline=True,
    )
    assert outcome.degraded is not None
    assert "quota" in outcome.degraded.lower()
    assert outcome.capture.completion.by_map > 0, "the deterministic fill still ran"
    assert outcome.capture.completion.by_fallback == 0


def test_a_dom_change_leaves_a_retrievable_artifact(
    store: LocalPackageStore, changed_form: Path, tmp_path: Path
) -> None:
    """A halt produces an artifact naming the field, at the completion it actually reached.

    Recording a halt as complete would be the same failure the Spike A figure was fixed for, on
    the one path where nobody would look for it.
    """
    outcome = run(
        application_id="app_1",
        posting_url="https://boards.greenhouse.io/acme/jobs/1",
        page=OfflineHtmlPage(changed_form),
        store=store,
        client=_client(tmp_path),
        artifacts=tmp_path / "artifacts",
        offline=True,
    )
    record = json.loads((outcome.artifact_dir / "run.json").read_text())
    assert record["halted"] is not None
    assert "job_application[email]" in record["halted"]

    assert outcome.capture.completion.rate < 1.0
    assert json.loads((store.root / "app_1.capture.json").read_text())["completion"] < 1.0
    named = {field["name"]: field["outcome"] for field in record["fields"]}
    assert named["job_application[email]"] == "unfilled", "the field it stopped on is named"
    assert "resolved" in named.values(), "the partial fill is in the capture too"


def test_the_workflow_reads_no_secret_from_the_tree() -> None:
    """Credentials come from Actions secrets only; the repository is public."""
    text = WORKFLOW.read_text()
    assert "secrets.GEMINI_API_KEY" in text
    assert "AIza" not in text, "an API key literal must never appear"


def test_the_workflow_serialises_dispatches_per_application() -> None:
    """A double dispatch queues rather than running two concurrent fills of one form."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    concurrency = workflow["concurrency"]
    assert "inputs.application_id" in concurrency["group"]
    assert concurrency["cancel-in-progress"] is False


def test_the_workflow_retains_the_artifact_even_on_failure() -> None:
    """A halted run's capture is uploaded, since that is the diagnostic evidence."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    upload = next(
        step for step in workflow["jobs"]["fill"]["steps"] if "upload-artifact" in str(step)
    )
    assert upload["if"] == "always()"
    assert upload["with"]["retention-days"] == 90


def test_no_workflow_step_submits_anything() -> None:
    """No executable step touches a submit path; the comments may discuss it, the steps may not."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    commands = " ".join(
        str(step.get("run", "")) + str(step.get("uses", ""))
        for step in workflow["jobs"]["fill"]["steps"]
    ).lower()
    assert "submit" not in commands


def test_a_question_no_recording_covers_degrades_rather_than_crashing(
    store: LocalPackageStore, tmp_path: Path
) -> None:
    """With no live transport wired yet (issue #18), a novel question leaves an artifact."""
    client = ModelClient(golden_root=tmp_path / "golden")
    outcome = run(
        application_id="app_1",
        posting_url="https://boards.greenhouse.io/acme/jobs/1",
        page=OfflineHtmlPage(ATS_FIXTURES / "greenhouse" / "custom-questions.html"),
        store=store,
        client=client,
        artifacts=tmp_path / "artifacts",
        offline=True,
    )
    assert outcome.degraded is not None
    assert outcome.capture.halted is None, "a missing recording degrades rather than halting"
    assert outcome.capture.completion.by_map > 0, "the deterministic fill still ran"
    assert (outcome.artifact_dir / "run.json").exists()


def test_the_workflow_passes_dispatch_inputs_through_the_environment() -> None:
    """Interpolating a caller's text into a step holding secrets is the injection pattern."""
    workflow = yaml.safe_load(WORKFLOW.read_text())
    fill = next(step for step in workflow["jobs"]["fill"]["steps"] if step.get("id") == "fill")
    assert "inputs." not in fill["run"], "dispatch inputs reach the shell as variables"
    assert fill["env"]["APPLICATION_ID"] == "${{ inputs.application_id }}"
    assert fill["env"]["POSTING_URL"] == "${{ inputs.posting_url }}"
