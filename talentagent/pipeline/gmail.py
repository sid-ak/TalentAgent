"""Reading the user's mailbox, read-only, through the one permitted outbound path (Spec §4.3).

Three properties are worth stating before the code, because each is a deliberate limit rather than
an omission.

The scope is `gmail.readonly` and nothing else. There is no send scope, so there is no path from
here to a message leaving the user's account — the same shape as Pass 2, where the guarantee is the
absence of a method rather than a check that could be refactored away (G3).

No credential is stored by the system. The refresh token is supplied by the environment, the access
token lives for the length of one request, and neither is written to disk or included in any model
call. Obtaining the refresh token is a separate, human-run step (`scripts/gmail_auth.py`), so the
consent screen is a thing the user sees rather than something an agent drives (G6).

Every message body comes back as `UntrustedText`. Mail is the most hostile input the system takes:
it is attacker-controlled, arrives unsolicited, and is read by a model. It enters as data through
the same wrapper as everything else, and the injection scan runs on it (G7).
"""

from __future__ import annotations

import base64
import json
import os
import urllib.parse
from dataclasses import dataclass
from typing import Any

from talentagent.net.fetch import Fetcher, default_fetcher
from talentagent.net.untrusted import UntrustedText, wrap_untrusted

TOKEN_URL = "https://oauth2.googleapis.com/token"
"""Where a refresh token is exchanged for a short-lived access token."""

MESSAGES_URL = "https://gmail.googleapis.com/gmail/v1/users/me/messages"
"""The list-and-get endpoint for the authenticated user's own mail."""

READONLY_SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
"""The only scope this system ever asks for. Read, never send (G3)."""

DEFAULT_QUERY = (
    "newer_than:60d ("
    "subject:(application OR interview OR role OR position OR candidate OR recruiter)"
    " OR from:(greenhouse OR lever OR ashby OR workday OR recruiting OR talent OR careers))"
)
"""A deliberately narrow default search.

Pulling a whole mailbox to classify it would be both slower and a wider read than the job needs.
Gmail's own query language does the coarse filter for free, before anything is fetched, and tier 1
sees only what plausibly concerns an application (Spec §8.1).
"""

MAX_MESSAGES = 15
"""How many messages one sync reads. A ceiling on both the read and the tier-1 payload."""


class GmailNotConfigured(RuntimeError):
    """Raised when the Gmail credentials are absent from the environment."""

    def __init__(self) -> None:
        """Name what is missing and how the user supplies it."""
        super().__init__(
            "Gmail is not connected. Set GMAIL_CLIENT_ID, GMAIL_CLIENT_SECRET, and "
            "GMAIL_REFRESH_TOKEN. Obtain the refresh token by running "
            "`python scripts/gmail_auth.py`, which walks you through Google's consent screen "
            "and prints the token; nothing else in the system can obtain one."
        )


class GmailError(RuntimeError):
    """Raised when Gmail refuses a request, carrying what it said."""


@dataclass(frozen=True)
class GmailCredentials:
    """An OAuth client and the user's refresh token, supplied by the environment."""

    client_id: str
    client_secret: str
    refresh_token: str

    @classmethod
    def from_env(cls) -> GmailCredentials | None:
        """Return credentials from the environment, or None when any part is absent."""
        client_id = os.environ.get("GMAIL_CLIENT_ID", "").strip()
        client_secret = os.environ.get("GMAIL_CLIENT_SECRET", "").strip()
        refresh_token = os.environ.get("GMAIL_REFRESH_TOKEN", "").strip()
        if not (client_id and client_secret and refresh_token):
            return None
        return cls(client_id, client_secret, refresh_token)


def access_token(credentials: GmailCredentials, fetcher: Fetcher | None = None) -> str:
    """Exchange the refresh token for a short-lived access token.

    Raises:
        GmailError: if the exchange is refused.
    """
    response = (fetcher or default_fetcher).post_form(
        TOKEN_URL,
        {
            "client_id": credentials.client_id,
            "client_secret": credentials.client_secret,
            "refresh_token": credentials.refresh_token,
            "grant_type": "refresh_token",
        },
    )
    payload = json.loads(response.as_data())
    token = payload.get("access_token")
    if not token:
        raise GmailError(f"Token exchange returned no access token: {payload.get('error')}")
    return str(token)


def _decode(data: str) -> str:
    """Decode one base64url body part, tolerating the padding Gmail omits."""
    return base64.urlsafe_b64decode(data + "=" * (-len(data) % 4)).decode("utf-8", errors="replace")


def _plain_text(payload: dict[str, Any]) -> str:
    """Return the text/plain body of a message payload, walking nested parts.

    Prefers `text/plain` over `text/html` because the HTML alternative of a recruiting email is
    mostly layout, and layout is tokens tier 1 would be charged for reading.
    """
    if payload.get("mimeType") == "text/plain":
        data = payload.get("body", {}).get("data")
        if data:
            return _decode(data)
    for part in payload.get("parts", []) or []:
        found = _plain_text(part)
        if found:
            return found
    data = payload.get("body", {}).get("data")
    return _decode(data) if data else ""


def _headers(payload: dict[str, Any]) -> dict[str, str]:
    """Return the message headers we render, lowercased by name."""
    wanted = {"from", "subject", "date"}
    return {
        h["name"].lower(): h.get("value", "")
        for h in payload.get("headers", []) or []
        if h.get("name", "").lower() in wanted
    }


def _render(message: dict[str, Any]) -> str:
    """Render one Gmail message as the flat text the classifier reads."""
    payload = message.get("payload", {})
    headers = _headers(payload)
    body = _plain_text(payload).strip() or str(message.get("snippet", ""))
    return (
        f"From: {headers.get('from', 'unknown')}\n"
        f"Date: {headers.get('date', '')}\n"
        f"Subject: {headers.get('subject', '(no subject)')}\n\n"
        f"{body[:1500]}"
    )


def recent_messages(
    credentials: GmailCredentials,
    query: str = DEFAULT_QUERY,
    limit: int = MAX_MESSAGES,
    fetcher: Fetcher | None = None,
) -> list[UntrustedText]:
    """Read up to `limit` recent messages matching `query`, newest first.

    Raises:
        GmailError: if Gmail refuses the list or a fetch.
    """
    use = fetcher or default_fetcher
    token = access_token(credentials, use)
    auth = {"Authorization": f"Bearer {token}"}

    listing = json.loads(
        use.fetch(
            f"{MESSAGES_URL}?maxResults={int(limit)}&q={_quote(query)}", headers=auth
        ).as_data()
    )
    if "error" in listing:
        raise GmailError(str(listing["error"].get("message", listing["error"])))

    rendered: list[UntrustedText] = []
    for stub in listing.get("messages", [])[:limit]:
        raw = use.fetch(f"{MESSAGES_URL}/{stub['id']}?format=full", headers=auth).as_data()
        message = json.loads(raw)
        if "error" in message:
            continue
        rendered.append(wrap_untrusted(_render(message), source="gmail.googleapis.com"))

    rendered.reverse()
    return rendered


def _quote(value: str) -> str:
    """Percent-encode a Gmail search query for use in a URL."""
    return urllib.parse.quote(value, safe="")
