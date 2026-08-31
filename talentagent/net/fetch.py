"""The single outbound read path for the whole system.

Two guardrails live here, and one of them is here only because of the budget constraint.

G5 was a VPC egress policy in the original design. There is no network-layer egress control on
Actions runners or in Apps Script, so the permitted-domain list moved into this wrapper, enforced by
code and asserted in tests (Architecture 6.2, ADR-0012). That is a genuine weakening relative to an
infrastructure control, and it is the clearest single reason to migrate if the constraint lifts.

G7 is unchanged in strength but concentrated here: every value this module returns is
`UntrustedText`.
"""

from __future__ import annotations

import urllib.parse
import urllib.request
from collections.abc import Mapping
from pathlib import Path
from typing import Protocol
from urllib.parse import urlparse

import yaml

from talentagent.net.untrusted import UntrustedText, wrap_untrusted

_ALLOWLIST_PATH = Path(__file__).parent / "allowlist.yaml"

DEFAULT_TIMEOUT = 30.0
"""How long to wait on an outbound read before giving up, in seconds."""


class Transport(Protocol):
    """Signature of a transport: take a request, return the response body.

    Injected so the suite can run with no network at all (ADR-0012) without stubbing the allowlist
    check out along with it. `headers` and `data` exist because some permitted hosts need a bearer
    token or a form post — Gmail needs both — and routing those through a second code path would
    mean G5 and G7 had two chokepoints to hold instead of one.
    """

    def __call__(
        self,
        url: str,
        timeout: float,
        *,
        headers: Mapping[str, str] | None = None,
        data: bytes | None = None,
    ) -> bytes:
        """Perform the request and return the raw response body."""
        ...


class AllowlistViolation(RuntimeError):
    """Raised when a fetch targets a domain absent from the permitted-domain list.

    This is a refusal, not a warning. A domain that is not listed is out of scope by design.
    """

    def __init__(self, host: str) -> None:
        """Record the host that was refused."""
        self.host = host
        super().__init__(
            f"{host!r} is not on the permitted-domain allowlist (G5). Add it to "
            f"talentagent/net/allowlist.yaml if it is genuinely in scope."
        )


def load_allowlist(path: Path | None = None) -> frozenset[str]:
    """Load the permitted domains, flattened across their grouping keys."""
    raw = yaml.safe_load((path or _ALLOWLIST_PATH).read_text())
    return frozenset(host for group in raw.values() for host in group)


def _urllib_transport(
    url: str,
    timeout: float,
    *,
    headers: Mapping[str, str] | None = None,
    data: bytes | None = None,
) -> bytes:
    """Fetch `url` with the standard library. The only outbound HTTP call in the system."""
    merged = {"User-Agent": "TalentAgent/0.1", **(headers or {})}
    request = urllib.request.Request(url, headers=merged, data=data)
    with urllib.request.urlopen(request, timeout=timeout) as response:  # noqa: S310
        body: bytes = response.read()
    return body


class Fetcher:
    """Performs outbound reads, enforcing G5 on the way out and G7 on the way back."""

    def __init__(
        self,
        allowlist: frozenset[str] | None = None,
        transport: Transport | None = None,
    ) -> None:
        """Build a fetcher over a permitted-domain set and a transport."""
        self._allowlist = load_allowlist() if allowlist is None else allowlist
        self._transport = transport or _urllib_transport

    def is_permitted(self, url: str) -> bool:
        """Report whether `url`'s host is on the allowlist."""
        host = urlparse(url).hostname
        return host is not None and host in self._allowlist

    def check(self, url: str) -> str:
        """Return the host of `url`, or raise if it is not permitted.

        Raises:
            AllowlistViolation: if the host is absent from the permitted-domain list.
        """
        host = urlparse(url).hostname
        if host is None or host not in self._allowlist:
            raise AllowlistViolation(host or url)
        return host

    def fetch(
        self,
        url: str,
        timeout: float = DEFAULT_TIMEOUT,
        *,
        headers: Mapping[str, str] | None = None,
        data: bytes | None = None,
    ) -> UntrustedText:
        """Read `url` and return its body as untrusted third-party text.

        Passing `data` makes this a POST, which the OAuth token exchange needs. A response is
        untrusted whichever verb produced it: reading a mailbox is the most hostile input the
        system takes, and it arrives through here like everything else.

        Raises:
            AllowlistViolation: if the host is not permitted.
            InjectionAttempt: if the response tries to issue instructions.
        """
        host = self.check(url)
        body = self._transport(url, timeout, headers=headers, data=data)
        return wrap_untrusted(body.decode("utf-8", errors="replace"), source=host)

    def post_form(
        self,
        url: str,
        fields: Mapping[str, str],
        timeout: float = DEFAULT_TIMEOUT,
    ) -> UntrustedText:
        """Post `fields` as a urlencoded form and return the response.

        Raises:
            AllowlistViolation: if the host is not permitted.
        """
        return self.fetch(
            url,
            timeout,
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            data=urllib.parse.urlencode(dict(fields)).encode(),
        )


default_fetcher = Fetcher()
"""The process-wide fetcher. Components take a `Fetcher` where they need to inject a transport."""


def fetch(url: str, timeout: float = DEFAULT_TIMEOUT) -> UntrustedText:
    """Read `url` through the default fetcher."""
    return default_fetcher.fetch(url, timeout)
