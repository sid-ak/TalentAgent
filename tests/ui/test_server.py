"""Tests for the TalentAgent UI server endpoints and data handlers (Phase 2.5).

Pins the REST API responses, candidate profile ingestion, statement promotion, and ATS fills.
"""

from __future__ import annotations

from typing import Any
from unittest.mock import MagicMock

from talentagent.ui.server import TalentAgentUIHandler


class DummyRequest:
    """Mock socket request object for testing the HTTP handler."""

    def __init__(self, method: str, path: str, body: bytes = b"") -> None:
        """Initialize mock socket request."""
        self.method = method
        self.path = path
        self.body = body

    def makefile(self, *args: object, **kwargs: object) -> object:
        """Return dummy file streams for input and output."""
        import io

        if args and "r" in str(args[0]):
            return io.BytesIO(self.body)
        return io.BytesIO()


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


def test_profiles_endpoint() -> None:
    """Profiles endpoint returns metadata for Profile A, Profile B, and Custom candidates."""
    handler = TalentAgentUIHandler.__new__(TalentAgentUIHandler)
    sent_data: list[tuple[int, dict[str, Any]]] = []
    handler._send_json = lambda code, data: sent_data.append((code, data))  # type: ignore[assignment]
    handler.path = "/api/profiles"

    handler.do_GET()

    assert len(sent_data) == 1
    _, data = sent_data[0]
    profile_ids = [p["id"] for p in data["profiles"]]
    assert "profile_a" in profile_ids
    assert "profile_b" in profile_ids
    assert "custom" in profile_ids


def test_evidence_graph_endpoint() -> None:
    """Evidence graph endpoint returns nodes and edges with attestation information."""
    handler = TalentAgentUIHandler.__new__(TalentAgentUIHandler)
    sent_data: list[tuple[int, dict[str, Any]]] = []
    handler._send_json = lambda code, data: sent_data.append((code, data))  # type: ignore[assignment]
    handler.path = "/api/evidence-graph?profile_id=profile_a"

    handler.do_GET()

    assert len(sent_data) == 1
    _, data = sent_data[0]
    assert data["profile_id"] == "profile_a"
    assert len(data["nodes"]) > 0


def test_compose_and_promote_flow() -> None:
    """Compose package handles requirements and promote statement adds new knowledge."""
    handler = TalentAgentUIHandler.__new__(TalentAgentUIHandler)
    sent_data: list[tuple[int, dict[str, Any]]] = []
    handler._send_json = lambda code, data: sent_data.append((code, data))  # type: ignore[assignment]

    # Test compose against custom candidate
    compose_body = {
        "profile_id": "custom",
        "posting_id": "job_1",
        "requirements": ["5+ years of experience with Python development"],
    }
    handler._handle_compose(compose_body)
    assert len(sent_data) == 1
    _, comp_res = sent_data[-1]
    assert "package" in comp_res
    assert len(comp_res["package"]["bullets"]) > 0

    # Test statement promotion
    promote_body = {
        "profile_id": "custom",
        "answer": "Architected distributed cache invalidation reducing p99 latency by 50ms.",
        "skills": ["Distributed Systems"],
    }
    handler._handle_promote_statement(promote_body)
    _, prom_res = sent_data[-1]
    assert prom_res["status"] == "promoted"
    assert prom_res["attestation_class"] == "attested"
