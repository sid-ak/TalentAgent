"""Evidence sync: artifact ingest and candidate clustering (Spec §8.2, Issue §22).

Ingests commits, pull requests, and documents through the allowlisted fetch wrapper (G5), treats all
third-party text as data (G7), and clusters candidates strictly as `DERIVED` (Invariant 2).
Provides incremental sync with a persistent cursor and carries retrospective elicitation trigger 2.
"""

from __future__ import annotations

import datetime
import json
import re

from pydantic import BaseModel, ConfigDict, Field

from talentagent.evidence.graph import (
    Accomplishment,
    Artifact,
    ArtifactSubtype,
    AttestationClass,
    Edge,
    EdgeType,
    EvidencePeriod,
    Metric,
    NodeType,
)
from talentagent.evidence.store import EvidenceStore
from talentagent.net.fetch import Fetcher, default_fetcher


class SyncCursor(BaseModel):
    """Persisted sync cursor per repository source for incremental ingest."""

    model_config = ConfigDict(extra="forbid")

    source: str
    last_sync_time: str
    seen_shas: list[str] = Field(default_factory=list)
    seen_pr_numbers: list[int] = Field(default_factory=list)


def classify_artifact(url: str, is_public: bool = True) -> AttestationClass:
    """Mechanically classify an artifact based on public inspectability (ADR-0008)."""
    if is_public:
        return AttestationClass.VERIFIABLE
    return AttestationClass.CORROBORATED


def candidate_accomplishment(
    claim: str,
    evidence: list[str],
    skills: list[str] | None = None,
    metrics: list[Metric] | None = None,
    period: EvidencePeriod | None = None,
    confidence: float = 0.85,
    derived_by: str = "evidence_sync@2026",
) -> Accomplishment:
    """Factory producing candidate accomplishments strictly with class DERIVED (Invariant 2).

    Does not accept an attestation class parameter, ensuring all clustered output enters the graph
    quarantined by construction.
    """
    acc_id = f"acc_cand_{abs(hash(claim)) % 1000000:06d}"
    return Accomplishment(
        id=acc_id,
        claim=claim,
        skills=skills or [],
        metrics=metrics or [],
        evidence=evidence,
        period=period,
        confidence=confidence,
        derived_by=derived_by,
        attestation_class=AttestationClass.DERIVED,
    )


_METRIC_DELTA_PATTERN = re.compile(
    r"(?:reduced|cut|decreased|improved|boosted)\s+([a-zA-Z0-9_\s]+?)\s+(?:by\s+)?(\d+(?:\.\d+)?)\s*(%|percent|ratio|x)?",
    re.I,
)
_METRIC_COUNT_PATTERN = re.compile(
    r"(?:(?:migrated|instrumented|managed|across|for)\s+)?(\d+)\s+([a-zA-Z0-9_]+)(?:\s+services|\s+teams|\s+nodes|\s+to|\s+across|\s+for|\.|$)",
    re.I,
)


def extract_metrics(text: str, source_basis: str) -> list[Metric]:
    """Extract quantitative measurements stated in artifact text."""
    metrics: list[Metric] = []
    delta_match = _METRIC_DELTA_PATTERN.search(text)
    if delta_match:
        metric_name = delta_match.group(1).strip().lower().replace(" ", "_")
        val_str = delta_match.group(2)
        unit = "ratio" if delta_match.group(3) in ("%", "percent") else "scalar"
        delta = float(val_str)
        if unit == "ratio" and delta > 1.0:
            delta = delta / 100.0
        metrics.append(
            Metric(
                name=metric_name,
                delta=-delta if "reduced" in text.lower() or "cut" in text.lower() else delta,
                unit=unit,
                basis=source_basis,
            )
        )

    count_match = _METRIC_COUNT_PATTERN.search(text)
    if count_match:
        val = int(count_match.group(1))
        item = count_match.group(2).strip().lower().replace(" ", "_")
        metrics.append(
            Metric(
                name=f"{item}_count",
                value=val,
                unit="count",
                basis=source_basis,
            )
        )
    return metrics


class RetrospectiveQuestion(BaseModel):
    """A scoped elicitation question triggered by milestone or project close (Trigger 2)."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    milestone: str
    question: str
    """Requests specifics: quantity, timeframe, and user's role relative to team's (Spec §3.5)."""


def build_milestone_question(milestone_name: str, repo: str) -> RetrospectiveQuestion:
    """Build exactly one structured elicitation question for a closed milestone."""
    text = (
        f'Milestone "{milestone_name}" was recently completed in {repo}. '
        "What specific outcome did you drive, over what timeframe, and what quantitative metric "
        "or team impact resulted?"
    )
    return RetrospectiveQuestion(milestone=milestone_name, question=text)


class EvidenceSyncResult(BaseModel):
    """Summary of an evidence sync run."""

    model_config = ConfigDict(extra="forbid")

    source: str
    ingested_artifacts: int
    candidate_accomplishments: int
    retrospective_questions: list[RetrospectiveQuestion] = Field(default_factory=list)


def sync_github_repository(
    repo: str,
    store: EvidenceStore,
    fetcher: Fetcher | None = None,
    cursor: SyncCursor | None = None,
    is_public: bool = True,
) -> tuple[EvidenceSyncResult, SyncCursor]:
    """Incrementally ingest GitHub commits and PRs into the evidence store."""
    active_fetcher = fetcher or default_fetcher
    now_str = datetime.datetime.now(datetime.UTC).isoformat()

    if cursor is None:
        cursor = SyncCursor(source=repo, last_sync_time="1970-01-01T00:00:00Z")

    commits_url = f"https://api.github.com/repos/{repo}/commits"
    pulls_url = f"https://api.github.com/repos/{repo}/pulls?state=closed"

    ingested_artifacts: list[Artifact] = []
    retrospective_questions: list[RetrospectiveQuestion] = []

    # 1. Fetch commits
    try:
        commits_untrusted = active_fetcher.fetch(commits_url)
        commits_data = json.loads(commits_untrusted.as_data())
        if isinstance(commits_data, list):
            for c in commits_data:
                sha = c.get("sha", "")
                if sha in cursor.seen_shas:
                    continue
                msg = c.get("commit", {}).get("message", "")
                html_url = c.get("html_url", "")
                art = Artifact(
                    id=f"art_commit_{sha[:7]}",
                    subtype=ArtifactSubtype.COMMIT,
                    title=msg.split("\n")[0],
                    url=html_url,
                    source=f"github:{repo}",
                )
                store.save_node(art)
                ingested_artifacts.append(art)
                cursor.seen_shas.append(sha)
    except Exception:
        pass

    # 2. Fetch PRs
    try:
        pulls_untrusted = active_fetcher.fetch(pulls_url)
        pulls_data = json.loads(pulls_untrusted.as_data())
        if isinstance(pulls_data, list):
            for pr in pulls_data:
                num = pr.get("number", 0)
                if num in cursor.seen_pr_numbers:
                    continue
                title = pr.get("title", "")
                html_url = pr.get("html_url", "")
                art = Artifact(
                    id=f"art_pr_{num}",
                    subtype=ArtifactSubtype.PR,
                    title=f"PR #{num}: {title}",
                    url=html_url,
                    source=f"github:{repo}",
                )
                store.save_node(art)
                ingested_artifacts.append(art)
                cursor.seen_pr_numbers.append(num)

                # Check for milestone / project close keywords
                lower_title = title.lower()
                if "milestone" in lower_title or "release" in lower_title or "v1." in lower_title:
                    retrospective_questions.append(build_milestone_question(title, repo))
    except Exception:
        pass

    # 3. Cluster ingested artifacts into candidate accomplishments (DERIVED)
    candidate_count = 0
    if ingested_artifacts:
        ev_ids = [a.id for a in ingested_artifacts]
        combined_titles = "; ".join(a.title for a in ingested_artifacts[:3])
        claim = f"Contributed to {repo}: {combined_titles}"
        metrics = []
        for a in ingested_artifacts:
            metrics.extend(extract_metrics(a.title, f"github:{repo}"))

        cand = candidate_accomplishment(
            claim=claim,
            evidence=ev_ids,
            metrics=metrics,
            confidence=0.88,
        )
        store.save_node(cand)
        candidate_count = 1

        for ev_id in ev_ids:
            store.save_edge(
                Edge(
                    source_id=ev_id,
                    source_type=NodeType.ARTIFACT,
                    target_id=cand.id,
                    target_type=NodeType.ACCOMPLISHMENT,
                    edge_type=EdgeType.EVIDENCES,
                )
            )

    cursor.last_sync_time = now_str
    result = EvidenceSyncResult(
        source=repo,
        ingested_artifacts=len(ingested_artifacts),
        candidate_accomplishments=candidate_count,
        retrospective_questions=retrospective_questions,
    )
    return result, cursor
