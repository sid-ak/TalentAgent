"""Tests for evidence sync: ingest, clustering, metric attachment, and cursor state (Issue #22)."""

from collections.abc import Mapping
from pathlib import Path

import pytest
from talentagent.evidence.graph import (
    AttestationClass,
)
from talentagent.evidence.store import LocalEvidenceStore
from talentagent.evidence.sync import (
    candidate_accomplishment,
    classify_artifact,
    extract_metrics,
    sync_github_repository,
)
from talentagent.net.fetch import Fetcher

FIXTURE_API_DIR = (
    Path(__file__).parent.parent / "fixtures" / "evidence" / "profile_a" / "github_api"
)


@pytest.fixture
def mock_fetcher() -> Fetcher:
    """Return a Fetcher using the recorded GitHub API fixture responses."""
    commits_body = (FIXTURE_API_DIR / "commits.json").read_bytes()
    pulls_body = (FIXTURE_API_DIR / "pulls.json").read_bytes()

    def transport(
        url: str,
        timeout: float,
        *,
        headers: Mapping[str, str] | None = None,
        data: bytes | None = None,
    ) -> bytes:
        if "commits" in url:
            return commits_body
        if "pulls" in url:
            return pulls_body
        raise ValueError(f"Unexpected url: {url}")

    return Fetcher(allowlist=frozenset(["api.github.com"]), transport=transport)


def test_classify_artifact_mechanical() -> None:
    """Artifact classification is deterministic based on inspectability (ADR-0008)."""
    assert (
        classify_artifact("https://github.com/example/repo", is_public=True)
        == AttestationClass.VERIFIABLE
    )
    assert (
        classify_artifact("https://internal.gitlab/repo", is_public=False)
        == AttestationClass.CORROBORATED
    )


def test_candidate_accomplishment_is_strictly_derived() -> None:
    """Candidate accomplishments are created with class DERIVED and no override path."""
    acc = candidate_accomplishment(
        claim="Clustered claim",
        evidence=["art_1", "art_2"],
    )
    assert acc.attestation_class == AttestationClass.DERIVED
    assert acc.confidence is not None


def test_metric_extraction() -> None:
    """Metrics are extracted only when explicitly stated in text with basis recorded."""
    m1 = extract_metrics("Reduced p99 ingest latency by 62%", "github:pr_412")
    assert len(m1) >= 1
    assert m1[0].name == "p99_ingest_latency"
    assert m1[0].delta == -0.62
    assert m1[0].basis == "github:pr_412"

    m2 = extract_metrics("Migrated 40 services to new auth", "github:pr_500")
    assert len(m2) >= 1
    assert m2[0].value == 40
    assert m2[0].unit == "count"


def test_sync_github_repository_and_incremental_cursor(
    tmp_path: Path, mock_fetcher: Fetcher
) -> None:
    """Sync ingests artifacts, clusters candidate accomplishments, and advances cursor."""
    store = LocalEvidenceStore(tmp_path / "sync_store")

    # Run 1: fresh sync
    res1, cursor1 = sync_github_repository(
        repo="example/talentagent-repo",
        store=store,
        fetcher=mock_fetcher,
    )
    assert res1.ingested_artifacts >= 2
    assert res1.candidate_accomplishments >= 1
    assert len(cursor1.seen_shas) >= 2
    assert len(cursor1.seen_pr_numbers) >= 2

    # Assert candidate accomplishments in store are all DERIVED
    quarantined = store.quarantined()
    assert len(quarantined) >= 1
    for q in quarantined:
        assert q.attestation_class == AttestationClass.DERIVED

    # Assert active() has zero DERIVED accomplishments (G1)
    assert len(store.active()) == 0

    # Run 2: incremental with cursor -> ingests 0 new artifacts
    res2, cursor2 = sync_github_repository(
        repo="example/talentagent-repo",
        store=store,
        fetcher=mock_fetcher,
        cursor=cursor1,
    )
    assert res2.ingested_artifacts == 0
    assert res2.candidate_accomplishments == 0
