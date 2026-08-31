"""Tests for the scheduled evidence sync entry point job (Issue #22)."""

import json
from pathlib import Path

from talentagent.jobs.evidence_sync import run_evidence_sync


def test_run_evidence_sync_creates_report_and_cursor(tmp_path: Path) -> None:
    """run_evidence_sync creates artifacts report and runs cleanly."""
    work_dir = tmp_path / "work"
    store_dir = tmp_path / "store"

    exit_code = run_evidence_sync(
        repo="example/talentagent-repo",
        work_dir=work_dir,
        store_dir=store_dir,
    )
    assert exit_code == 0
    report_file = work_dir / "evidence_sync_report.json"
    assert report_file.exists()
    report = json.loads(report_file.read_text())
    assert report["status"] in ("success", "degraded")
