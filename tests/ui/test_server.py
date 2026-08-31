"""Tests for the TalentAgent UI server endpoints and data handlers.

Pins the REST API responses, candidate profile ingestion, statement promotion, and ATS fills.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from talentagent.ui.server import GLOBAL_SESSION, TalentAgentUIHandler


def test_status_endpoint() -> None:
    """Status endpoint returns health, active guardrails, and quota metrics."""
    mock_server = MagicMock()
    mock_request = MagicMock()

    handler = TalentAgentUIHandler.__new__(TalentAgentUIHandler)
    handler.server = mock_server
    handler.request = mock_request
    handler.headers = MagicMock()
    handler.path = "/api/status"

    sent_data: list[tuple[int, dict[str, Any]]] = []

    def mock_send_json(status_code: int, data: Any) -> None:
        sent_data.append((status_code, data))

    handler._send_json = mock_send_json  # type: ignore[method-assign]
    handler.do_GET()

    assert len(sent_data) == 1
    status_code, data = sent_data[0]
    assert status_code == 200
    assert data["status"] == "healthy"
    assert data["guardrails"]["G1"]["active"] is True
    assert data["guardrails"]["G2"]["active"] is True
    assert data["guardrails"]["G3"]["active"] is True
    assert "quotas" in data


def test_profile_and_statement_flow() -> None:
    """Profile endpoint allows updating identity and adding statements."""
    GLOBAL_SESSION.reset()
    handler = TalentAgentUIHandler.__new__(TalentAgentUIHandler)
    sent_data: list[tuple[int, dict[str, Any]]] = []

    def mock_send(status_code: int, data: Any) -> None:
        sent_data.append((status_code, data))

    handler._send_json = mock_send  # type: ignore[method-assign]

    # Update candidate profile
    update_body = {
        "identity": {
            "first_name": "Jordan",
            "last_name": "Lee",
            "email": "jordan.lee@example.com",
            "location": "Seattle, WA",
        },
        "links": {
            "github": "https://github.com/jordanlee",
        },
    }
    handler._handle_update_profile(update_body)
    assert len(sent_data) == 1
    _, prof_res = sent_data[-1]
    assert prof_res["identity"]["first_name"] == "Jordan"
    assert prof_res["has_profile"] is True

    # Add raw statement
    stmt_body = {
        "raw_text": "Architected streaming distributed pub/sub pipeline in Python.",
        "skills": ["Python", "Distributed Systems"],
    }
    handler._handle_add_statement(stmt_body)
    _, stmt_res = sent_data[-1]
    assert stmt_res["status"] == "added"
    assert stmt_res["attestation_class"] == "attested"

    # Verify graph now has nodes
    handler._handle_evidence_graph()
    _, graph_res = sent_data[-1]
    assert len(graph_res["nodes"]) > 0

    # Compose package against requirement
    compose_body = {
        "posting_id": "job_python_lead",
        "requirements": ["5+ years of experience with Python development"],
    }
    handler._handle_compose(compose_body)
    _, comp_res = sent_data[-1]
    assert "package" in comp_res
    assert len(comp_res["package"]["bullets"]) > 0
