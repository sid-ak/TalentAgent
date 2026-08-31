"""Pins the Spike A gate: the threshold, the table, and a platform that falls short."""

import json
from pathlib import Path

import pytest
from talentagent.ats.completion import Completion
from talentagent.ats.gate import THRESHOLD, GateReport, PlatformResult, report_from_captures
from talentagent.jobs.spike_a_gate import main, run_all

pytestmark = pytest.mark.slow


def test_every_platform_meets_the_threshold(tmp_path: Path) -> None:
    """The Spike A criterion, measured across all twelve fixtures with no network."""
    report = run_all(tmp_path)
    assert {r.platform for r in report.results} == {"greenhouse", "lever", "ashby"}
    for result in report.results:
        assert result.completion.rate >= THRESHOLD, (
            f"{result.platform} is at {result.completion.rate:.1%}; a platform below the "
            f"threshold is dropped rather than the criterion lowered"
        )
    assert report.passed


def test_the_measurement_is_reproducible(tmp_path: Path) -> None:
    """The same command produces the same table, so the figure is a measurement not an anecdote."""
    first = run_all(tmp_path / "a").to_markdown()
    second = run_all(tmp_path / "b").to_markdown()
    assert first == second


def test_the_report_is_read_from_the_captures_a_reviewer_sees(tmp_path: Path) -> None:
    """The gate recomputes nothing, so the reported figure cannot drift from the reviewed one."""
    run_all(tmp_path)
    assert (
        report_from_captures(tmp_path / "artifacts").to_markdown()
        == run_all(tmp_path / "again").to_markdown()
    )


def test_the_deterministic_share_is_below_the_completion_rate(tmp_path: Path) -> None:
    """Custom questions are answered by the fallback, so the two figures must differ."""
    for result in run_all(tmp_path).results:
        assert result.completion.by_fallback > 0
        assert result.completion.deterministic_share < result.completion.rate


def test_every_fixture_produced_a_capture_and_none_halted(tmp_path: Path) -> None:
    """Twelve runs, twelve retrievable captures, no halts (G3 is asserted in the executor suite)."""
    run_all(tmp_path)
    records = sorted((tmp_path / "artifacts").rglob("run.json"))
    assert len(records) == 12
    assert all(json.loads(r.read_text())["halted"] is None for r in records)


def test_a_platform_below_the_threshold_fails_the_gate() -> None:
    """The gate reports a drop rather than rounding up to a pass."""
    weak = PlatformResult("weak", Completion(by_map=8, by_fallback=0, unfilled=2), fixtures=4)
    report = GateReport((weak,))
    assert weak.completion.rate == pytest.approx(0.8)
    assert not report.passed
    assert report.failing == ("weak",)
    assert "DROP" in report.to_markdown()


def test_the_gate_command_exits_non_zero_when_a_platform_falls_short(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, capsys: pytest.CaptureFixture[str]
) -> None:
    """CI fails the phase check rather than producing a warning."""
    monkeypatch.setattr(
        "talentagent.jobs.spike_a_gate.run_all",
        lambda _work: GateReport(
            (PlatformResult("weak", Completion(by_map=1, by_fallback=0, unfilled=9), 4),)
        ),
    )
    assert main(["--work", str(tmp_path)]) == 1
    assert "ADR-0011" in capsys.readouterr().err


def test_the_gate_command_exits_zero_on_the_real_fixtures(tmp_path: Path) -> None:
    """The command a human runs is the command CI runs."""
    assert main(["--work", str(tmp_path)]) == 0
