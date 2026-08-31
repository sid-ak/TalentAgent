"""Evidence retrieval and per-requirement sufficiency scoring (Spec §9.1, §5.3, Issue #23).

Computes deterministic requirement normalisation and calculates numeric sufficiency
outside the model (ADR-0008). Ensures `DERIVED` nodes are barred from candidate retrieval
at the store boundary (Invariant 2, G1).
"""

from __future__ import annotations

import re

from pydantic import BaseModel, ConfigDict, Field

from talentagent.evidence.graph import (
    Accomplishment,
    AttestationClass,
)
from talentagent.evidence.store import EvidenceStore

DEFAULT_SUFFICIENCY_THRESHOLD = 0.6
"""Minimum sufficiency score required to proceed with composition (Spec §5.3, Issue #23).

A requirement scoring below 0.6 produces a gap (FLAG if partial evidence exists, ELICIT if none),
preventing the model from inventing claims for weakly evidenced requirements.
"""


class NormalizedRequirement(BaseModel):
    """Normalized representation of an employer requirement from a job posting."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    id: str
    text: str
    skills: list[str] = Field(default_factory=list)
    min_years: int | None = None
    required_metrics: list[str] = Field(default_factory=list)


_KNOWN_SKILL_KEYWORDS: dict[str, str] = {
    "python": "skill_python",
    "pubsub": "skill_pubsub",
    "pub/sub": "skill_pubsub",
    "distributed systems": "skill_distributed_systems",
    "distributed": "skill_distributed_systems",
    "auth": "skill_auth",
    "authentication": "skill_auth",
    "migration": "skill_migration",
    "leadership": "skill_leadership",
    "kubernetes": "skill_kubernetes",
    "k8s": "skill_kubernetes",
    "product strategy": "skill_product_strategy",
    "stakeholder management": "skill_stakeholder_management",
    "stakeholder": "skill_stakeholder_management",
    "operations": "skill_operations",
    "rust": "skill_rust",
    "go": "skill_go",
    "golang": "skill_go",
    "aws": "skill_aws",
    "gcp": "skill_gcp",
    "azure": "skill_azure",
    "sql": "skill_sql",
    "c#": "skill_csharp",
    "csharp": "skill_csharp",
    ".net": "skill_dotnet",
    "dotnet": "skill_dotnet",
    "javascript": "skill_javascript",
    "typescript": "skill_typescript",
    "angular": "skill_angular",
    "react": "skill_react",
    "node": "skill_node",
    "nodejs": "skill_node",
    "docker": "skill_docker",
    "java": "skill_java",
    "api": "skill_api",
    "rest": "skill_api",
    "graphql": "skill_graphql",
    "agile": "skill_agile",
    "data analysis": "skill_data_analysis",
}


def extract_posting_requirements(content: str) -> list[str]:
    """Extract clean, discrete requirement strings from a job posting HTML or plain text.

    Strips DOM markup, scripts, and navigation boilerplate, returning candidate qualifications.
    """
    if "<html" in content.lower() or "<body" in content.lower() or "<div" in content.lower():
        try:
            import lxml.html as lxml_html

            tree = lxml_html.fromstring(content)
            elements = tree.xpath("//script | //style | //noscript | //header | //footer | //nav")
            if isinstance(elements, list):
                for elem in elements:
                    if isinstance(elem, lxml_html.HtmlElement) and elem.getparent() is not None:
                        elem.getparent().remove(elem)

            # Look for structured list items in the job description
            requirements: list[str] = []
            lis = tree.xpath("//li")
            if isinstance(lis, list):
                for li in lis:
                    if isinstance(li, lxml_html.HtmlElement):
                        text = " ".join(li.text_content().split())
                        if len(text) > 15:
                            requirements.append(text)

            if requirements:
                return requirements

            # Fallback to substantive paragraphs
            ps = tree.xpath("//p")
            if isinstance(ps, list):
                for p in ps:
                    if isinstance(p, lxml_html.HtmlElement):
                        text = " ".join(p.text_content().split())
                        if len(text) > 25 and not text.startswith("©"):
                            requirements.append(text)

            if requirements:
                return requirements
        except Exception:
            pass

    # Plain text line splitting
    lines = [line.strip() for line in content.splitlines() if len(line.strip()) > 15]
    clean_lines: list[str] = []
    for line in lines:
        cleaned = re.sub(r"^[•\-\*\d\.]+\s*", "", line)
        if len(cleaned) > 15 and not cleaned.startswith("<"):
            clean_lines.append(cleaned)
    return clean_lines


def normalise_requirement(
    text: str,
    requirement_id: str | None = None,
) -> NormalizedRequirement:
    """Deterministically extract skills and parameters from a requirement string."""
    req_id = requirement_id or f"req_{abs(hash(text)) % 10000:04d}"
    lower_text = text.lower()

    # Extract skills
    found_skills: list[str] = []
    for kw, skill_id in sorted(_KNOWN_SKILL_KEYWORDS.items(), key=lambda x: -len(x[0])):
        if kw in lower_text and skill_id not in found_skills:
            found_skills.append(skill_id)

    # Extract years of experience
    years_match = re.search(r"(\d+)\+?\s*(?:years?|yrs?)\b", lower_text)
    min_years = int(years_match.group(1)) if years_match else None

    return NormalizedRequirement(
        id=req_id,
        text=text,
        skills=found_skills,
        min_years=min_years,
    )


def score_candidate(requirement: NormalizedRequirement, cand: Accomplishment) -> float:
    """Score an individual candidate against a normalized requirement."""
    req_skills_set = set(requirement.skills)
    cand_skills_set = set(cand.skills)
    matched_skills = req_skills_set.intersection(cand_skills_set)

    skill_coverage = len(matched_skills) / len(req_skills_set) if req_skills_set else 0.8
    score = skill_coverage * 0.7

    if cand.metrics:
        score += 0.2

    multiplier = 1.0
    if cand.attestation_class == AttestationClass.CORROBORATED:
        multiplier = 0.95
    elif cand.attestation_class == AttestationClass.ATTESTED:
        multiplier = 0.90

    return min(1.0, score * multiplier)


def calculate_sufficiency(
    requirement: NormalizedRequirement,
    candidates: list[Accomplishment],
) -> float:
    """Calculate a deterministic, reproducible sufficiency score in [0.0, 1.0].

    Degenerate case: returns exactly 0.0 when no candidates are present.
    """
    if not candidates:
        return 0.0

    scores = [score_candidate(requirement, c) for c in candidates]
    best_candidate_score = max(scores)

    if len(candidates) > 1 and best_candidate_score > 0.0:
        best_candidate_score = min(1.0, best_candidate_score + 0.05)

    return round(best_candidate_score, 2)


class RetrievalResult(BaseModel):
    """The output of an evidence retrieval query for one requirement."""

    model_config = ConfigDict(extra="forbid")

    requirement: NormalizedRequirement
    candidates: list[Accomplishment]
    sufficiency: float
    classes: list[AttestationClass]
    meets_threshold: bool


def query_evidence(
    requirement: str | NormalizedRequirement,
    store: EvidenceStore,
    threshold: float = DEFAULT_SUFFICIENCY_THRESHOLD,
) -> RetrievalResult:
    """Retrieve ranked admissible evidence candidates and compute requirement sufficiency."""
    norm_req = normalise_requirement(requirement) if isinstance(requirement, str) else requirement

    # Search active non-derived accomplishments across the store
    candidates: list[Accomplishment] = []
    seen_ids: set[str] = set()

    for skill_id in norm_req.skills:
        for acc in store.by_skill(skill_id):
            if acc.id not in seen_ids:
                candidates.append(acc)
                seen_ids.add(acc.id)

    # Sort candidates deterministically by score descending, then by ID
    candidates.sort(key=lambda a: (-score_candidate(norm_req, a), a.id))

    sufficiency = calculate_sufficiency(norm_req, candidates)
    classes = [c.attestation_class for c in candidates]
    meets_threshold = sufficiency >= threshold

    return RetrievalResult(
        requirement=norm_req,
        candidates=candidates,
        sufficiency=sufficiency,
        classes=classes,
        meets_threshold=meets_threshold,
    )
