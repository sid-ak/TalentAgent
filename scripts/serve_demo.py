#!/usr/bin/env python3
"""Launcher script for the TalentAgent review surface.

Host and port fall back to the HOST and PORT environment variables before their defaults, which
is how Cloud Run starts a container: it injects PORT and expects the process to listen on
0.0.0.0. Locally, with neither set, the defaults keep the server on loopback.

Usage:
    python scripts/serve_demo.py [--port 8080] [--host 127.0.0.1]
"""

from __future__ import annotations

import argparse
import os
import sys

from talentagent.ui.server import DEFAULT_PORT, run_server


def main() -> None:
    """Parse CLI arguments and run UI server."""
    parser = argparse.ArgumentParser(description="TalentAgent Review UI Server")
    parser.add_argument(
        "--port",
        type=int,
        default=int(os.environ.get("PORT", DEFAULT_PORT)),
        help="Port to listen on (default: $PORT, else 8080)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default=os.environ.get("HOST", "127.0.0.1"),
        help="Host address (default: $HOST, else 127.0.0.1)",
    )
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
