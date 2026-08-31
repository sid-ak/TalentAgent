#!/usr/bin/env python3
"""One-time helper: obtain a Gmail refresh token through Google's consent screen.

Run by a human, never by an agent. The point of keeping this out of the application is that
granting access to a mailbox should be something the account holder does, sees, and can revoke —
not something a running service can arrange for itself (G6).

It asks for `gmail.readonly` and nothing else, so the token it produces cannot send mail.

Usage:
    python3 scripts/gmail_auth.py --client-id ... --client-secret ...

Uses only the standard library, so it needs no virtualenv and no dependencies installed.

Prints the refresh token. Put it in .env as GMAIL_REFRESH_TOKEN alongside GMAIL_CLIENT_ID and
GMAIL_CLIENT_SECRET, or pass all three to Cloud Run as environment variables.
"""

from __future__ import annotations

import argparse
import http.server
import json
import secrets
import sys
import threading
import urllib.parse
import urllib.request
import webbrowser

AUTH_URL = "https://accounts.google.com/o/oauth2/v2/auth"
TOKEN_URL = "https://oauth2.googleapis.com/token"
SCOPE = "https://www.googleapis.com/auth/gmail.readonly"
PORT = 8765
REDIRECT = f"http://localhost:{PORT}/"


class _Catcher(http.server.BaseHTTPRequestHandler):
    """Catches the single redirect Google makes back to localhost."""

    code: str | None = None
    state: str | None = None

    def do_GET(self) -> None:  # noqa: N802
        """Record the authorization code and tell the human they can close the tab."""
        params = urllib.parse.parse_qs(urllib.parse.urlparse(self.path).query)
        _Catcher.code = params.get("code", [None])[0]
        _Catcher.state = params.get("state", [None])[0]
        body = b"<h2>TalentAgent: authorised.</h2><p>You can close this tab.</p>"
        self.send_response(200)
        self.send_header("Content-Type", "text/html")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *_args: object) -> None:
        """Stay quiet; the useful output is the token."""


def main() -> None:
    """Run the consent flow and print the resulting refresh token."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--client-id", required=True)
    parser.add_argument("--client-secret", required=True)
    args = parser.parse_args()

    state = secrets.token_urlsafe(16)
    query = urllib.parse.urlencode(
        {
            "client_id": args.client_id,
            "redirect_uri": REDIRECT,
            "response_type": "code",
            "scope": SCOPE,
            "access_type": "offline",
            "prompt": "consent",
            "state": state,
        }
    )

    server = http.server.HTTPServer(("localhost", PORT), _Catcher)
    threading.Thread(target=server.handle_request, daemon=True).start()

    url = f"{AUTH_URL}?{query}"
    print(f"\nOpening Google's consent screen. If nothing opens, visit:\n\n{url}\n")
    webbrowser.open(url)

    while _Catcher.code is None:
        pass
    server.server_close()

    if _Catcher.state != state:
        sys.exit("State mismatch; aborting rather than trusting the redirect.")

    payload = urllib.parse.urlencode(
        {
            "code": _Catcher.code,
            "client_id": args.client_id,
            "client_secret": args.client_secret,
            "redirect_uri": REDIRECT,
            "grant_type": "authorization_code",
        }
    ).encode()
    request = urllib.request.Request(TOKEN_URL, data=payload)
    with urllib.request.urlopen(request, timeout=30) as response:  # noqa: S310
        tokens = json.loads(response.read())

    refresh = tokens.get("refresh_token")
    if not refresh:
        sys.exit(f"No refresh token returned. Google said: {tokens}")

    print("\nAdd this to .env, or set it on Cloud Run:\n")
    print(f"GMAIL_REFRESH_TOKEN={refresh}\n")


if __name__ == "__main__":
    main()
