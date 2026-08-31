"""TalentAgent interactive review surface and demo API server (Phase 2.5).

Provides HTTP endpoints and static assets serving the Angular review UI for candidate profile
management, evidence graph exploration, credited composition review, and ATS execution playback.
"""

from __future__ import annotations

__all__ = ["create_ui_server", "run_server"]

from talentagent.ui.server import create_ui_server, run_server
