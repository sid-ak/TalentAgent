#!/usr/bin/env python3
"""Launcher script for the TalentAgent Review Surface & Demo Server (Phase 2.5).

Usage:
    python scripts/serve_demo.py [--port 8080] [--host 127.0.0.1]
"""

from __future__ import annotations

import argparse
import sys

from talentagent.ui.server import DEFAULT_PORT, run_server


def main() -> None:
    """Parse CLI arguments and run UI server."""
    parser = argparse.ArgumentParser(description="TalentAgent Review UI Server")
    parser.add_argument(
        "--port", type=int, default=DEFAULT_PORT, help="Port to listen on (default 8080)"
    )
    parser.add_argument(
        "--host", type=str, default="127.0.0.1", help="Host address (default 127.0.0.1)"
    )
    args = parser.parse_args()

    run_server(host=args.host, port=args.port)


if __name__ == "__main__":
    main()
