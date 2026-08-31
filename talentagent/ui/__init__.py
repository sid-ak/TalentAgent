"""TalentAgent interactive review surface and demo API server (Phase 2.5).

Provides the HTTP endpoints and the static single-page review surface: candidate evidence
capture, the agent loop over a posting, credited composition, and ATS form execution.
"""

from __future__ import annotations

__all__ = ["create_ui_server", "run_server"]

from talentagent.ui.server import create_ui_server, run_server
