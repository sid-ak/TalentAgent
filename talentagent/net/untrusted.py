"""The type that keeps third-party text out of the instruction slot.

G7 says postings, inbound messages, and ATS page content are data and never instruction. A rule
everyone has to remember is not a guarantee, so the rule is carried by a type: third-party text
arrives as `UntrustedText`, which the prompt builders will not accept where instructions go. Reading
the underlying string requires saying so, at which point the call site is the thing under review.
"""

from __future__ import annotations

import re
from dataclasses import dataclass

# Phrases that attempt to redirect a model reading the content. Not exhaustive, and not meant to be:
# the guarantee is the type above, and this is defence in depth that also gives us a count of how
# often it is tried. Spec 10, note on G7.
_INJECTION_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"ignore\s+(all\s+)?(the\s+)?(previous|prior|above|preceding)", re.I),
    re.compile(r"disregard\s+(all\s+)?(the\s+)?(previous|prior|above|preceding)", re.I),
    re.compile(r"forget\s+(all\s+)?(your|the)\s+(previous|prior)\s+instructions", re.I),
    re.compile(r"you\s+are\s+now\s+a", re.I),
    re.compile(r"new\s+(system\s+)?instructions?\s*:", re.I),
    re.compile(r"(reveal|print|output)\s+(your|the)\s+(system\s+)?prompt", re.I),
)


class InjectionAttempt(RuntimeError):
    """Raised when third-party content tries to issue instructions.

    Handling is to halt the workflow instance rather than continue on best effort (Spec 10).
    """

    def __init__(self, source: str, matched: str) -> None:
        """Record where the attempt came from and the phrase that matched."""
        self.source = source
        self.matched = matched
        super().__init__(f"Injection attempt in content from {source}: {matched!r}")


@dataclass(frozen=True)
class UntrustedText:
    """Third-party text, carried in a type that cannot stand in for an instruction string.

    Attributes:
        source: Where the text came from, for logging and for the injection report.
    """

    _text: str
    source: str

    def as_data(self) -> str:
        """Return the raw text, for use as a data field only.

        Named so that a call site placing this into an instruction context is visible in review.
        """
        return self._text

    def __len__(self) -> int:
        """Return the length of the underlying text."""
        return len(self._text)

    def __str__(self) -> str:
        """Return a redacted description, so accidental interpolation cannot leak content."""
        return f"<UntrustedText from {self.source}: {len(self._text)} chars>"

    __repr__ = __str__


def scan_for_injection(text: str) -> str | None:
    """Return the first injection phrase found in `text`, or None if there is none."""
    for pattern in _INJECTION_PATTERNS:
        match = pattern.search(text)
        if match:
            return match.group(0)
    return None


def wrap_untrusted(text: str, source: str) -> UntrustedText:
    """Wrap third-party text, halting if it attempts to issue instructions.

    Raises:
        InjectionAttempt: if the content contains a known redirection phrase.
    """
    matched = scan_for_injection(text)
    if matched is not None:
        raise InjectionAttempt(source, matched)
    return UntrustedText(text, source)
