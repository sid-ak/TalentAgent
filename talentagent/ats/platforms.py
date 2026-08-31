"""Which platform a posting URL belongs to, and when two URLs are the same posting.

The build targets three platforms and no others (ADR-0010), so the host is what decides whether a
posting can be filled at all. Keeping that mapping here rather than in the worker means the live
page backend can share it: Greenhouse serves the same posting from more than one host, and a
comparison that did not know they were the same site would read a routine redirect as a navigation
away from the form.
"""

from __future__ import annotations

from urllib.parse import urlparse

PLATFORM_BY_HOST = {
    "boards.greenhouse.io": "greenhouse",
    "job-boards.greenhouse.io": "greenhouse",
    "jobs.lever.co": "lever",
    "jobs.ashbyhq.com": "ashby",
}
"""Maps a posting host to the platform whose field map applies to it. Greenhouse appears twice
because it serves postings from both hosts and redirects between them.
"""


class UnsupportedPlatform(ValueError):
    """Raised when a posting URL is not one of the three targeted platforms."""

    def __init__(self, host: str) -> None:
        """Name the host that has no field map."""
        self.host = host
        super().__init__(
            f"No field map for {host!r}. The build targets Greenhouse, Lever, and Ashby "
            f"(ADR-0010); a platform below 90% on fixtures is dropped rather than half-supported."
        )


def platform_for(url: str) -> str:
    """Return the platform a posting URL belongs to.

    Raises:
        UnsupportedPlatform: if there is no map for its host.
    """
    host = urlparse(url).hostname or ""
    if host not in PLATFORM_BY_HOST:
        raise UnsupportedPlatform(host)
    return PLATFORM_BY_HOST[host]


def same_posting(one: str, other: str) -> bool:
    """Report whether two URLs address the same posting.

    Fragments and a trailing slash are ignored, and two hosts serving the same platform count as
    the same site. Used to tell a host redirect apart from a navigation away from the form, which
    is how a submission would show itself (G3).
    """
    left, right = urlparse(one), urlparse(other)
    if left.path.rstrip("/") != right.path.rstrip("/"):
        return False
    if left.hostname == right.hostname:
        return True
    known = PLATFORM_BY_HOST.get(left.hostname or "")
    return known is not None and known == PLATFORM_BY_HOST.get(right.hostname or "")
