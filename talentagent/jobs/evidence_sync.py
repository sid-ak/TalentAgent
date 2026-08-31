"""Scheduled evidence sync job entry point (Spec §8.2, Issue #22).

Runs the evidence sync for designated repository sources, updates the graph store, tracks cursor
state, and emits a structured run artifact.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from talentagent.evidence.store import LocalEvidenceStore
from talentagent.evidence.sync import SyncCursor, sync_github_repository
from talentagent.models.client import GoldenResponseMissing, QuotaExhausted
from talentagent.net.fetch import default_fetcher
from talentagent.net.untrusted import InjectionAttempt


def run_evidence_sync(
    repo: str,
    work_dir: Path,
    store_dir: Path | None = None,
) -> int:
    """Execute evidence sync for `repo`, writing reports and persisting state."""
    work_dir.mkdir(parents=True, exist_ok=True)
    report_file = work_dir / "evidence_sync_report.json"
    safe_repo = repo.replace("/", "_")
    cursor_file = work_dir / f"cursor_{safe_repo}.json"

    store = LocalEvidenceStore(store_dir or (work_dir / "evidence_store"))

    cursor = None
    if cursor_file.exists():
        try:
            cursor = SyncCursor.model_validate_json(cursor_file.read_text())
        except Exception:
            cursor = None

    try:
        result, new_cursor = sync_github_repository(
            repo=repo,
            store=store,
            fetcher=default_fetcher,
            cursor=cursor,
        )
        cursor_file.write_text(new_cursor.model_dump_json(indent=2))
        report_data = {
            "status": "success",
            "repo": repo,
            "ingested_artifacts": result.ingested_artifacts,
            "candidate_accomplishments": result.candidate_accomplishments,
            "retrospective_questions": [q.model_dump() for q in result.retrospective_questions],
        }
        report_file.write_text(json.dumps(report_data, indent=2))
        return 0

    except (GoldenResponseMissing, QuotaExhausted, InjectionAttempt) as e:
        report_data = {
            "status": "degraded",
            "repo": repo,
            "error_type": type(e).__name__,
            "error_message": str(e),
        }
        report_file.write_text(json.dumps(report_data, indent=2))
        return 0

    except Exception as e:
        report_data = {
            "status": "error",
            "repo": repo,
            "error_type": type(e).__name__,
            "error_message": str(e),
        }
        report_file.write_text(json.dumps(report_data, indent=2))
        return 1


def main() -> None:
    """Parse CLI arguments and run the sync job."""
    parser = argparse.ArgumentParser(description="TalentAgent scheduled evidence sync")
    parser.add_argument(
        "--repo",
        default="example/talentagent-repo",
        help="Repository to sync (owner/repo)",
    )
    parser.add_argument(
        "--work",
        type=Path,
        default=Path(".talentagent/evidence_sync"),
        help="Working directory for artifacts",
    )
    parser.add_argument(
        "--store",
        type=Path,
        default=None,
        help="Evidence store directory",
    )
    args = parser.parse_args()

    exit_code = run_evidence_sync(repo=args.repo, work_dir=args.work, store_dir=args.store)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
