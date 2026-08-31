"""Pins tiering, replay, quota accounting, and backoff (issue #5)."""

import json
from pathlib import Path

import pytest
from talentagent.models.client import (
    GoldenResponseMissing,
    ModelCall,
    ModelClient,
    QuotaExhausted,
    QuotaLedger,
    RateLimited,
    Tier,
)


@pytest.fixture
def golden(tmp_path: Path) -> Path:
    """An empty golden-response root, isolated per test."""
    return tmp_path / "golden"


def _record(golden: Path, call: ModelCall, response: dict[str, object]) -> None:
    """Write a golden response for `call`, as record mode would."""
    path = golden / call.tier.value / f"{call.key()}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"response": response}))


def test_replay_returns_the_recorded_response_and_makes_no_call(golden: Path) -> None:
    """A replayed call answers from disk; the autouse zero-network fixture proves it went nowhere.

    That is the whole quota control: replay is only a saving if nothing can bypass it.
    """
    call = ModelCall(Tier.ONE, "classify", {"subject": "Your application"}, "triage_v1")
    _record(golden, call, {"is_job_related": True})
    client = ModelClient(golden_root=golden)
    assert client.call(call) == {"is_job_related": True}


def test_a_missing_fixture_names_a_real_recovery_path(golden: Path) -> None:
    """The failure names something a contributor can actually run.

    It previously named `python -m talentagent.models.record`, a module that does not exist, so
    the documented recovery for the project's central quota control was a dead end.
    """
    client = ModelClient(golden_root=golden)
    with pytest.raises(GoldenResponseMissing, match="record=True") as caught:
        client.tier_two("compose", {"requirement": "req_1"}, "package_v1")
    assert "talentagent.models.record" not in str(caught.value)


def test_the_key_is_stable_across_input_ordering() -> None:
    """The same inputs produce the same fixture, so recordings are not invalidated by dict order."""
    first = ModelCall(Tier.TWO, "p", {"a": 1, "b": 2}, "s")
    second = ModelCall(Tier.TWO, "p", {"b": 2, "a": 1}, "s")
    assert first.key() == second.key()


def test_tier_changes_the_fixture(golden: Path) -> None:
    """A tier-1 recording cannot be served to a tier-2 call, so tiering cannot drift unnoticed."""
    one = ModelCall(Tier.ONE, "p", {}, "s")
    two = ModelCall(Tier.TWO, "p", {}, "s")
    _record(golden, one, {"tier": "one"})
    client = ModelClient(golden_root=golden)
    assert client.call(one) == {"tier": "one"}
    with pytest.raises(GoldenResponseMissing):
        client.call(two)


def test_tier_ceilings_match_the_architecture_budget() -> None:
    """Flash-Lite carries four times Flash's allowance, which is why triage is routed to it."""
    assert Tier.ONE.daily_limit == 1000
    assert Tier.TWO.daily_limit == 250
    assert Tier.ONE.daily_limit == 4 * Tier.TWO.daily_limit


def test_quota_exhaustion_is_its_own_outcome_and_is_not_retried(golden: Path) -> None:
    """Reaching the daily ceiling raises QuotaExhausted so callers degrade rather than spin."""
    ledger = QuotaLedger()
    for _ in range(Tier.TWO.daily_limit):
        ledger.consume(Tier.TWO)
    with pytest.raises(QuotaExhausted):
        ledger.consume(Tier.TWO)
    assert ledger.report()["gemini-flash"] == {"used": 250, "limit": 250}


def test_rate_limits_back_off_within_the_run(golden: Path) -> None:
    """A rate limit is retried with exponential backoff; the delays are asserted, not slept."""
    attempts = {"n": 0}
    delays: list[float] = []

    def transport(_call: ModelCall) -> dict[str, object]:
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise RateLimited
        return {"ok": True}

    client = ModelClient(golden_root=golden, transport=transport, record=True, sleep=delays.append)
    assert client.tier_one("classify", {}, "triage_v1") == {"ok": True}
    assert delays == [1.0, 2.0], "backoff must be exponential"


def test_recording_writes_a_replayable_fixture(golden: Path) -> None:
    """A recorded call can be replayed byte for byte by a later client in replay mode."""

    def transport(_call: ModelCall) -> dict[str, object]:
        return {"answer": "4"}

    call = ModelCall(Tier.TWO, "years of python", {"q": "q_yoe"}, "screening_v1")
    ModelClient(golden_root=golden, transport=transport, record=True).call(call)
    assert ModelClient(golden_root=golden).call(call) == {"answer": "4"}
