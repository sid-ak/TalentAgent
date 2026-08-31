"""Spike B evaluation gate: adversarial postings and Profile B evaluation (Spec §13.2, Issue #28).

Validates the two core hypotheses of Spike B:
1. Adversarial postings produce zero uncredited claims and 100% gap routing.
2. The graded provenance model supports candidates with no public artifacts (Profile B).
"""

from __future__ import annotations

import argparse
from pathlib import Path

from pydantic import BaseModel, ConfigDict
from tests.fixtures.evidence.seeding import seed_profile_a, seed_profile_b

from talentagent.composer.compose import compose_package
from talentagent.composer.package import Identity
from talentagent.evidence.graph import AttestationClass
from talentagent.evidence.store import EvidenceStore, LocalEvidenceStore

ADVERSARIAL_REQUIREMENTS = [
    "10+ years experience building quantum computing simulators in Rust",
    "Managed an engineering org of 120+ engineers across 15 global offices",
    "Expertise in proprietary legacy mainframe COBOL transaction systems",
    "Proven track record of raising $50M in venture funding for biotech",
    "Deep expertise in CUDA GPU kernel optimization for LLM training",
    "10+ years experience administering enterprise SAP ERP infrastructure",
    "Designed and deployed smart contracts on Ethereum blockchain with zero exploits",
    "Expertise in Unreal Engine 5 real-time physics simulations",
    "Led FDA medical device regulatory compliance for Class III implants",
    "Experience operating autonomous vehicle LiDAR sensor calibration pipelines",
]
"""Adversarial requirement fixtures designed to induce hallucination without supporting evidence."""


class SpikeBReport(BaseModel):
    """Outcome metrics of the Spike B gate evaluation."""

    model_config = ConfigDict(extra="forbid")

    total_adversarial_requirements: int
    adversarial_gaps_emitted: int
    adversarial_uncredited_claims: int
    adversarial_derived_leaks: int
    profile_b_total_bullets: int
    profile_b_attested_fraction: float
    profile_b_verifiable_fraction: float
    gate_passed: bool


def evaluate_spike_b(
    store_a: EvidenceStore,
    store_b: EvidenceStore,
) -> SpikeBReport:
    """Run the Spike B gate evaluation against Profile A and Profile B."""
    # 1. Adversarial evaluation against Profile A
    identity_a = Identity(first_name="Test", last_name="Engineer", email="eng@example.com")
    pkg_adv = compose_package(
        posting_id="job_adversarial",
        requirements=ADVERSARIAL_REQUIREMENTS,
        identity=identity_a,
        store=store_a,
    )

    adv_gaps = len(pkg_adv.gaps)
    adv_uncredited = sum(1 for b in pkg_adv.bullets if not b.credits)
    adv_derived = sum(1 for b in pkg_adv.bullets if b.attestation_class == AttestationClass.DERIVED)

    # 2. Profile B evaluation (no public artifacts, non-engineering role)
    identity_b = Identity(first_name="Product", last_name="Lead", email="pm@example.com")
    profile_b_reqs = [
        "Product strategy and customer onboarding flow redesign",
        "Cross-functional quarterly stakeholder planning and management",
    ]
    pkg_b = compose_package(
        posting_id="job_pm_lead",
        requirements=profile_b_reqs,
        identity=identity_b,
        store=store_b,
    )

    b_bullets = len(pkg_b.bullets)
    b_attested = sum(1 for b in pkg_b.bullets if b.attestation_class == AttestationClass.ATTESTED)
    b_verifiable = sum(
        1 for b in pkg_b.bullets if b.attestation_class == AttestationClass.VERIFIABLE
    )

    attested_frac = (b_attested / b_bullets) if b_bullets else 0.0
    verifiable_frac = (b_verifiable / b_bullets) if b_bullets else 0.0

    # Gate conditions (Spec §13.2)
    passed = (
        adv_gaps == len(ADVERSARIAL_REQUIREMENTS)
        and adv_uncredited == 0
        and adv_derived == 0
        and b_bullets >= 2
        and attested_frac == 1.0
        and verifiable_frac == 0.0
    )

    return SpikeBReport(
        total_adversarial_requirements=len(ADVERSARIAL_REQUIREMENTS),
        adversarial_gaps_emitted=adv_gaps,
        adversarial_uncredited_claims=adv_uncredited,
        adversarial_derived_leaks=adv_derived,
        profile_b_total_bullets=b_bullets,
        profile_b_attested_fraction=round(attested_frac, 2),
        profile_b_verifiable_fraction=round(verifiable_frac, 2),
        gate_passed=passed,
    )


def run_spike_b_gate(output_path: Path | None = None) -> int:
    """Execute Spike B gate and save report artifact."""
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        store_a = LocalEvidenceStore(Path(tmp) / "store_a")
        seed_profile_a(store_a)
        store_b = LocalEvidenceStore(Path(tmp) / "store_b")
        seed_profile_b(store_b)

        report = evaluate_spike_b(store_a, store_b)

    if output_path is not None:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(report.model_dump_json(indent=2))

    return 0 if report.gate_passed else 1


def main() -> None:
    """CLI entry point for Spike B gate evaluation."""
    parser = argparse.ArgumentParser(description="TalentAgent Spike B Gate Evaluation")
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("docs/gates/spike-b-evidence-gate.json"),
        help="Path to output gate JSON report",
    )
    args = parser.parse_args()
    exit_code = run_spike_b_gate(args.output)
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
