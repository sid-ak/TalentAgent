"""Tests asserting that Spike B gate passes unconditionally (Spec §13.2, Issue #28)."""

from pathlib import Path

import pytest
from talentagent.evidence.store import LocalEvidenceStore
from talentagent.jobs.spike_b_gate import evaluate_spike_b, run_spike_b_gate

from tests.fixtures.evidence.seeding import seed_profile_a, seed_profile_b


@pytest.fixture
def store_a(tmp_path: Path) -> LocalEvidenceStore:
    """Return store seeded with Profile A."""
    st = LocalEvidenceStore(tmp_path / "store_a")
    seed_profile_a(st)
    return st


@pytest.fixture
def store_b(tmp_path: Path) -> LocalEvidenceStore:
    """Return store seeded with Profile B."""
    st = LocalEvidenceStore(tmp_path / "store_b")
    seed_profile_b(st)
    return st


def test_spike_b_gate_evaluation_passes(
    store_a: LocalEvidenceStore, store_b: LocalEvidenceStore
) -> None:
    """Spike B evaluation satisfies 100% gap routing and Profile B attested purity."""
    report = evaluate_spike_b(store_a, store_b)
    assert report.gate_passed is True
    assert report.adversarial_gaps_emitted == report.total_adversarial_requirements
    assert report.adversarial_uncredited_claims == 0
    assert report.adversarial_derived_leaks == 0
    assert report.profile_b_attested_fraction == 1.0
    assert report.profile_b_verifiable_fraction == 0.0


def test_spike_b_gate_runner_emits_json_report(tmp_path: Path) -> None:
    """run_spike_b_gate executes cleanly and writes report file."""
    out_path = tmp_path / "spike_b_gate.json"
    exit_code = run_spike_b_gate(out_path)
    assert exit_code == 0
    assert out_path.exists()
