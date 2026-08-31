"""The field map and its resolver: the mechanism that keeps the model out of the DOM.

A map takes a stable field identity on a page and gives a path into the application package,
deterministically, per platform. Deciding what to say is a reasoning problem over evidence;
deciding where to put it is a mechanical problem over a DOM. A single agentic browser loop fails at
both at once and cannot be tested without hitting real endpoints (ADR-0008).

The part of the schema that does the most work is the one that lets a map say it will not handle a
field. An employer-authored question named `answers_attributes[3][text_value]` carries nothing a map
could key on, and a demographic question should never be answered by an agent at all. Both are
misses, they are different misses, and reporting them honestly is what the Spike A completion figure
is measured against.
"""

from __future__ import annotations

import enum
import re
from dataclasses import dataclass
from pathlib import Path

import yaml

MAP_ROOT = Path(__file__).parent / "maps"

_LABEL_NOISE = re.compile(r"[\s*✱†]+$|\s*\(required\)\s*$|\s*\*\s*$", re.I)
"""Trailing required-marker glyphs and words the platforms decorate their labels with. Stripped
before comparison so a map keys on the label a human reads.
"""


class Strategy(enum.Enum):
    """How a rule identifies a field.

    The precedence order is the declaration order here, and it is deliberate. `name` is the most
    stable identity a platform exposes and is what its own backend keys on. `label` is what a human
    reads and survives an internal rename. `aria` is last because it is the least consistently
    present, but Ashby labels several built-in controls with nothing else.

    A rule may declare more than one, which is what makes a map survive a cosmetic DOM change: if
    the `name` attribute moves, the label still resolves it, and the converse.
    """

    NAME = "name"
    LABEL = "label"
    ARIA = "aria"


class MissReason(enum.Enum):
    """Why a field was not filled. These are different failures and are reported separately."""

    NO_RULE = "no_rule"
    """No rule in the map matched. Expected for employer-authored questions, and the input to the
    bounded model fallback (issue #15).
    """
    DECLARED_UNMAPPED = "declared_unmapped"
    """A rule matched and declared the field deliberately unhandled — a demographic question,
    say. The fallback must not touch these either.
    """
    NO_VALUE = "no_value"
    """A rule matched and named a package path, but the package has nothing there."""
    NOT_VISIBLE = "not_visible"
    """A rule matched a field that is present in the DOM but not currently visible."""


class FieldMapError(ValueError):
    """Raised when a map file is malformed, so it fails at load rather than mid-run."""


@dataclass(frozen=True)
class FieldRule:
    """One entry in a platform's map.

    Attributes:
        match: Identity strategies to try, in precedence order, mapped to the value to match.
        path: Dotted package path supplying the value, or None if the field is declared unmapped.
        unmapped: Set when the map recognises the field and deliberately declines to fill it.
        note: Why, where the reason is not obvious. Read by nobody at runtime and by everybody
            in review.
    """

    match: dict[Strategy, str]
    path: str | None = None
    unmapped: bool = False
    note: str = ""

    def matches(self, name: str, label: str | None, aria: str | None) -> bool:
        """Report whether this rule identifies the given field, trying strategies in precedence."""
        candidates = {Strategy.NAME: name, Strategy.LABEL: label, Strategy.ARIA: aria}
        for strategy in Strategy:
            expected = self.match.get(strategy)
            if expected is None:
                continue
            actual = candidates[strategy]
            if actual is not None and normalise(actual) == normalise(expected):
                return True
        return False


@dataclass(frozen=True)
class FieldMap:
    """Every rule for one platform."""

    platform: str
    rules: tuple[FieldRule, ...]

    def rule_for(self, name: str, label: str | None, aria: str | None) -> FieldRule | None:
        """Return the first rule identifying this field, or None if the map does not cover it."""
        for rule in self.rules:
            if rule.matches(name, label, aria):
                return rule
        return None


def normalise(text: str) -> str:
    """Reduce a label or name to the form comparisons are made in.

    Lowercased, internal whitespace collapsed, and the required-marker decoration stripped, so a map
    keying on "Email" still matches a label rendered as "Email *".
    """
    collapsed = " ".join(text.split())
    return _LABEL_NOISE.sub("", collapsed).strip().lower()


def load_map(platform: str, root: Path | None = None) -> FieldMap:
    """Load and validate one platform's field map.

    Raises:
        FieldMapError: if the file is malformed, so a bad map fails at load rather than mid-run.
    """
    path = (root or MAP_ROOT) / f"{platform}.yaml"
    if not path.exists():
        raise FieldMapError(f"No field map for platform {platform!r} at {path}")
    raw = yaml.safe_load(path.read_text())
    if not isinstance(raw, dict) or "rules" not in raw:
        raise FieldMapError(f"{path} must be a mapping with a 'rules' key")

    rules: list[FieldRule] = []
    for index, entry in enumerate(raw["rules"]):
        where = f"{path} rule {index}"
        match_raw = entry.get("match")
        if not isinstance(match_raw, dict) or not match_raw:
            raise FieldMapError(f"{where}: 'match' must name at least one identity strategy")
        try:
            match = {Strategy(key): str(value) for key, value in match_raw.items()}
        except ValueError as exc:
            raise FieldMapError(f"{where}: unknown identity strategy ({exc})") from exc

        path_value = entry.get("path")
        unmapped = bool(entry.get("unmapped", False))
        if unmapped == bool(path_value):
            raise FieldMapError(
                f"{where}: a rule declares exactly one of 'path' or 'unmapped: true'"
            )
        rules.append(
            FieldRule(
                match=match,
                path=path_value,
                unmapped=unmapped,
                note=str(entry.get("note", "")),
            )
        )
    return FieldMap(platform=str(raw.get("platform", platform)), rules=tuple(rules))
