"""The Spike A measurement harness.

The gate for the highest-risk work in the project, and it is passed with numbers rather than with a
sense that things are working. It is also allowed to fail: a platform that cannot reach the
threshold is dropped, and lowering the threshold is not one of the options (ADR-0011).

The harness recomputes nothing. It reads each run's capture, which is the same artifact a human
reviews, so the reported figure and the reviewed figure cannot drift apart.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

from talentagent.ats.completion import ZERO, Completion

THRESHOLD = 0.90
"""The Spike A threshold. A platform below this is dropped rather than the criterion lowered."""


@dataclass(frozen=True)
class PlatformResult:
    """One platform's measured completion across its whole fixture set."""

    platform: str
    completion: Completion
    fixtures: int

    @property
    def passed(self) -> bool:
        """Report whether this platform meets the Spike A threshold."""
        return self.completion.rate >= THRESHOLD


@dataclass(frozen=True)
class GateReport:
    """The completion table, and the verdict it implies."""

    results: tuple[PlatformResult, ...]

    @property
    def passed(self) -> bool:
        """Report whether every measured platform met the threshold."""
        return all(result.passed for result in self.results)

    @property
    def failing(self) -> tuple[str, ...]:
        """Return the platforms that would be dropped."""
        return tuple(r.platform for r in self.results if not r.passed)

    def to_markdown(self) -> str:
        """Render the table, which is what goes into the gate record."""
        lines = [
            "| Platform | Fixtures | Completion | Deterministic | Filled | By fallback | "
            "Unfilled | Declined | Verdict |",
            "|---|---|---|---|---|---|---|---|---|",
        ]
        for result in sorted(self.results, key=lambda r: r.platform):
            c = result.completion
            verdict = "pass" if result.passed else "DROP"
            lines.append(
                f"| {result.platform} | {result.fixtures} | {c.rate:.1%} | "
                f"{c.deterministic_share:.1%} | "
                f"{c.by_map + c.by_fallback} | {c.by_fallback} | {c.unfilled} | {c.declined} | "
                f"{verdict} |"
            )
        return "\n".join(lines)


def measure_platform(platform: str, captures: list[dict[str, object]]) -> PlatformResult:
    """Sum a platform's captures into one figure."""
    total = ZERO
    for capture in captures:
        raw = capture["completion"]
        assert isinstance(raw, dict)
        total = total + Completion(
            by_map=int(raw["by_map"]),
            by_fallback=int(raw["by_fallback"]),
            unfilled=int(raw["unfilled"]),
            declined=int(raw["declined"]),
            not_visible=int(raw["not_visible"]),
        )
    return PlatformResult(platform=platform, completion=total, fixtures=len(captures))


def report_from_captures(root: Path) -> GateReport:
    """Build the gate report from every `run.json` beneath `root`."""
    by_platform: dict[str, list[dict[str, object]]] = {}
    for record in sorted(root.rglob("run.json")):
        capture = json.loads(record.read_text())
        by_platform.setdefault(str(capture["platform"]), []).append(capture)
    return GateReport(
        results=tuple(
            measure_platform(platform, captures)
            for platform, captures in sorted(by_platform.items())
        )
    )
