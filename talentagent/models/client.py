"""The single model call path: tiering, quota accounting, and record-and-replay.

Every model call in the system goes through this client, so tiering and quota consumption are
properties of the system rather than habits of each caller.

Tier 1 is Flash-Lite and handles classification, which has a stable label set and sits on the
highest-volume path. Tier 2 is Flash and handles judgement. Pro-class models left the free tier on
1 April 2026, so tier 2 is the ceiling rather than a stop on the way to something larger
(Spec 9.2, ADR-0006).

Replay is the default everywhere, including CI. The recorded-response layer is the primary control
on the Gemini Flash daily quota, which has roughly 2x headroom against estimated use and is
consumed faster by development than by operation (ADR-0012, Architecture 8).
"""

from __future__ import annotations

import enum
import hashlib
import json
import time
from collections import Counter
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

GOLDEN_ROOT = Path(__file__).parent.parent.parent / "tests" / "fixtures" / "golden"
"""Where recorded responses live. Committed, and read by the suite instead of the network."""


class Tier(enum.Enum):
    """Which model answers a call, and what it is for (Spec 9.2)."""

    ONE = "gemini-flash-lite"
    """Classification of every inbound message and the posting-relevance filter. Four times the
    daily allowance of Flash, which is why the highest-volume path is routed here.
    """
    TWO = "gemini-flash"
    """State reasoning, requirement-to-evidence mapping, constrained composition, hypothesis
    formation — steps whose output is a judgement rather than a label.
    """

    @property
    def daily_limit(self) -> int:
        """Return the free-tier daily request ceiling for this tier (Architecture 8)."""
        return 1000 if self is Tier.ONE else 250


class GoldenResponseMissing(RuntimeError):
    """Raised in replay mode when no recorded response exists for a call."""

    def __init__(self, tier: Tier, key: str) -> None:
        """Name the missing fixture and the command that would record it."""
        self.tier = tier
        self.key = key
        super().__init__(
            f"No golden response for {tier.value} call {key}. The suite makes zero API calls "
            f"(ADR-0012). Record one by making the same call through a client built to record: "
            f"`ModelClient(transport=..., record=True)`, or `build_live_client()` from "
            f"`talentagent.models.live`, then copy the written file into "
            f"tests/fixtures/golden/{tier.value}/."
        )


class QuotaExhausted(RuntimeError):
    """Raised when a tier's daily ceiling is reached.

    Distinct from a rate limit and deliberately not retried: the mail path degrades to
    cursor-advance only and retries the next day, surfaced in the activity feed rather than
    failing silently (Architecture 7).
    """

    def __init__(self, tier: Tier) -> None:
        """Record which tier ran out."""
        self.tier = tier
        super().__init__(f"Daily quota exhausted for {tier.value}; degrade rather than retry.")


class RateLimited(RuntimeError):
    """Raised by a transport when the per-minute limit is hit. Retried with backoff in-run."""


@dataclass(frozen=True)
class ModelCall:
    """One request, in the form the golden key is computed from.

    Attributes:
        tier: Which model is being asked, recorded rather than inferred.
        prompt: The instruction text. Untrusted content never appears here (G7).
        data: Data fields, including anything third-party, kept separate from the instruction.
        schema_name: Names the response schema; a response failing it is a failure, not
            something to coerce.
    """

    tier: Tier
    prompt: str
    data: dict[str, Any]
    schema_name: str

    def key(self) -> str:
        """Return a stable hash of the call's inputs, used as the golden fixture name."""
        payload = json.dumps(
            {
                "tier": self.tier.value,
                "prompt": self.prompt,
                "data": self.data,
                "schema": self.schema_name,
            },
            sort_keys=True,
        )
        return hashlib.sha256(payload.encode()).hexdigest()[:16]


Transport = Callable[[ModelCall], dict[str, Any]]
"""A transport takes a call and returns the parsed response. Injected so the suite never needs
one.
"""


class QuotaLedger:
    """Counts requests per tier per day, so Spec 12's quota metric is a read not an estimate."""

    def __init__(self) -> None:
        """Start with nothing consumed."""
        self._counts: Counter[Tier] = Counter()

    def consume(self, tier: Tier) -> None:
        """Record one request against `tier`.

        Raises:
            QuotaExhausted: if the tier's daily ceiling has already been reached.
        """
        if self._counts[tier] >= tier.daily_limit:
            raise QuotaExhausted(tier)
        self._counts[tier] += 1

    def used(self, tier: Tier) -> int:
        """Return how many requests `tier` has consumed today."""
        return self._counts[tier]

    def report(self) -> dict[str, dict[str, int]]:
        """Return per-tier consumption against the ceiling, for the metrics surface."""
        return {
            tier.value: {"used": self._counts[tier], "limit": tier.daily_limit} for tier in Tier
        }


class ModelClient:
    """Routes model calls by tier, replaying recorded responses unless explicitly recording."""

    def __init__(
        self,
        golden_root: Path | None = None,
        transport: Transport | None = None,
        record: bool = False,
        ledger: QuotaLedger | None = None,
        max_retries: int = 3,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        """Build a client. With `record` false and no transport, only replay is possible."""
        self.golden_root = golden_root or GOLDEN_ROOT
        self._transport = transport
        self._record = record
        self.ledger = ledger or QuotaLedger()
        self._max_retries = max_retries
        self._sleep = sleep

    def _path(self, call: ModelCall) -> Path:
        """Return where the golden response for `call` lives."""
        return self.golden_root / call.tier.value / f"{call.key()}.json"

    def _replay(self, call: ModelCall) -> dict[str, Any]:
        """Return the recorded response for `call`.

        Raises:
            GoldenResponseMissing: if nothing has been recorded for it.
        """
        path = self._path(call)
        if not path.exists():
            raise GoldenResponseMissing(call.tier, call.key())
        recorded: dict[str, Any] = json.loads(path.read_text())["response"]
        return recorded

    def _live(self, call: ModelCall) -> dict[str, Any]:
        """Make a real call with backoff, and write the result as a golden fixture."""
        if self._transport is None:
            raise GoldenResponseMissing(call.tier, call.key())
        self.ledger.consume(call.tier)
        response = self._with_backoff(call)
        path = self._path(call)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(
                {
                    "tier": call.tier.value,
                    "prompt": call.prompt,
                    "data": call.data,
                    "schema": call.schema_name,
                    "response": response,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return response

    def _with_backoff(self, call: ModelCall) -> dict[str, Any]:
        """Call the transport, retrying a rate limit with exponential backoff within the run.

        A daily quota exhaustion is not retried: it is a different failure with a different
        remedy, and spinning on it wastes the little headroom that remains.
        """
        assert self._transport is not None
        for attempt in range(self._max_retries):
            try:
                return self._transport(call)
            except RateLimited:
                if attempt == self._max_retries - 1:
                    raise
                self._sleep(2.0**attempt)
        raise AssertionError("unreachable")

    def call(self, call: ModelCall) -> dict[str, Any]:
        """Answer `call`, from a recording unless the client was built to record."""
        return self._live(call) if self._record else self._replay(call)

    def tier_one(self, prompt: str, data: dict[str, Any], schema_name: str) -> dict[str, Any]:
        """Make a tier-1 call. The tier is chosen here by the call site, never inferred."""
        return self.call(ModelCall(Tier.ONE, prompt, data, schema_name))

    def tier_two(self, prompt: str, data: dict[str, Any], schema_name: str) -> dict[str, Any]:
        """Make a tier-2 call. The tier is chosen here by the call site, never inferred."""
        return self.call(ModelCall(Tier.TWO, prompt, data, schema_name))
