"""Tests for evidence retrieval, requirement normalisation, and sufficiency scoring (Issue #23)."""

from pathlib import Path

import pytest
from talentagent.evidence.graph import (
    Accomplishment,
    AttestationClass,
)
from talentagent.evidence.retrieval import (
    DEFAULT_SUFFICIENCY_THRESHOLD,
    NormalizedRequirement,
    calculate_sufficiency,
    extract_posting_requirements,
    normalise_requirement,
    query_evidence,
)
from talentagent.evidence.store import LocalEvidenceStore

from tests.fixtures.evidence.seeding import seed_profile_a


@pytest.fixture
def store_a(tmp_path: Path) -> LocalEvidenceStore:
    """Return a store seeded with Profile A."""
    store = LocalEvidenceStore(tmp_path / "store_a")
    seed_profile_a(store)
    return store


def test_normalise_requirement_extracts_skills_and_years() -> None:
    """Requirement normalisation extracts canonical skills and experience requirements."""
    req = normalise_requirement("5+ years of experience with Python and Pub/Sub in production")
    assert req.min_years == 5
    assert "skill_python" in req.skills
    assert "skill_pubsub" in req.skills


def test_degenerate_case_zero_candidates_returns_zero_sufficiency() -> None:
    """A requirement with no matching candidates produces exactly 0.0 sufficiency score."""
    req = NormalizedRequirement(
        id="req_k8s",
        text="Kubernetes cluster management",
        skills=["skill_kubernetes"],
    )
    score = calculate_sufficiency(req, [])
    assert score == 0.0


def test_sufficiency_is_reproducible(store_a: LocalEvidenceStore) -> None:
    """Sufficiency calculation is a pure function: same input produces identical score."""
    req = normalise_requirement("Experience optimizing Python latency and Pub/Sub pipelines")
    res1 = query_evidence(req, store_a)
    res2 = query_evidence(req, store_a)

    assert res1.sufficiency == res2.sufficiency
    assert res1.sufficiency >= DEFAULT_SUFFICIENCY_THRESHOLD
    assert res1.meets_threshold is True
    assert len(res1.candidates) >= 1
    assert all(c.attestation_class == AttestationClass.VERIFIABLE for c in res1.candidates)


def test_derived_nodes_excluded_from_retrieval(store_a: LocalEvidenceStore) -> None:
    """Derived nodes in the store are never included in retrieval result candidates (G1)."""
    # Inject a derived candidate
    cand = Accomplishment(
        id="acc_model_py",
        claim="Unconfirmed Python claim",
        skills=["skill_python"],
        evidence=["art_1"],
        attestation_class=AttestationClass.DERIVED,
    )
    store_a.save_node(cand)

    req = normalise_requirement("Python microservices")
    res = query_evidence(req, store_a)

    assert not any(c.id == "acc_model_py" for c in res.candidates)
    assert not any(c.attestation_class == AttestationClass.DERIVED for c in res.candidates)


def test_extract_posting_requirements_from_html_and_text() -> None:
    """Requirement extractor strips HTML markup and extracts discrete qualification bullets."""
    sample_html = """
    <html>
      <head><title>Job Title</title><script>var x = 1;</script></head>
      <body>
        <main>
          <h1>Senior Software Engineer</h1>
          <ul>
            <li>5+ years of experience with Python and distributed systems</li>
            <li>Hands-on experience with SQL database optimization</li>
          </ul>
        </main>
      </body>
    </html>
    """
    reqs = extract_posting_requirements(sample_html)
    assert len(reqs) == 2
    assert "5+ years of experience with Python and distributed systems" in reqs
    assert "Hands-on experience with SQL database optimization" in reqs

    # Plain text
    sample_text = """
    - 5+ years of experience with Kubernetes
    - Experience in microservices architecture
    """
    reqs_text = extract_posting_requirements(sample_text)
    assert len(reqs_text) == 2
    assert "5+ years of experience with Kubernetes" in reqs_text


def test_requirement_texts_accepts_both_shapes_the_model_returns() -> None:
    """Bare strings and objects both yield requirements, so neither shape drops the batch.

    Rejecting one shape meant falling back to line splitting with no error anywhere, which is how
    a model call goes missing unnoticed.
    """
    from talentagent.agent.loop import _requirement_texts

    assert _requirement_texts(["own Kubernetes", "write Go"]) == ["own Kubernetes", "write Go"]
    assert _requirement_texts([{"text": "own Kubernetes"}]) == ["own Kubernetes"]
    assert _requirement_texts([{"requirement": "write Go"}]) == ["write Go"]
    assert _requirement_texts([{"text": "  "}, None, 7]) == []
    assert _requirement_texts("not a list") == []
