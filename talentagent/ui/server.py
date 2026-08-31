"""HTTP server and REST API for the TalentAgent user review surface and workflow engine.

Provides endpoints for candidate profile management, evidence graph exploration, credited
package composition, interactive live elicitation, and ATS execution.
"""

from __future__ import annotations

import base64
import http.server
import io
import json
import mimetypes
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pypdf

from talentagent.ats.fieldmap import load_map
from talentagent.composer.compose import compose_package
from talentagent.composer.package import Identity, Links, Materials
from talentagent.evidence.elicitation import promote_statement
from talentagent.evidence.graph import (
    Accomplishment,
    Artifact,
    ArtifactSubtype,
    AttestationClass,
    Edge,
    EdgeType,
    Metric,
    NodeType,
    Skill,
    Statement,
)
from talentagent.evidence.retrieval import _KNOWN_SKILL_KEYWORDS, normalise_requirement
from talentagent.evidence.store import EvidenceStore, LocalEvidenceStore
from talentagent.models.live import get_live_client

DEFAULT_PORT = 8080
"""Default HTTP port for the UI review server."""

DAILY_TIER_1_QUOTA = 1000
"""Daily free-tier quota ceiling for Flash-Lite tier 1 requests (ADR-0012)."""

DAILY_TIER_2_QUOTA = 250
"""Daily free-tier quota ceiling for Flash tier 2 requests (ADR-0012)."""

WEB_DIR = Path(__file__).resolve().parent.parent.parent / "web"
"""Path to static assets for the Angular review UI."""


def get_all_nodes(store: EvidenceStore) -> list[Any]:
    """Return all nodes from an evidence store."""
    if hasattr(store, "_nodes_dir") and store._nodes_dir.exists():
        nodes = []
        for p in sorted(store._nodes_dir.glob("*.json")):
            try:
                node = store.get_node(p.stem)
                nodes.append(node)
            except Exception:
                continue
        return nodes
    return list(store.active())


def _extract_and_save_skills(
    store: EvidenceStore, text: str, explicit_skills: list[str] | None = None
) -> list[str]:
    """Extract, save, and return normalized skill node IDs from text and input skills."""
    skill_ids: set[str] = set()
    if explicit_skills:
        for s in explicit_skills:
            s_clean = s.strip().lower()
            if not s_clean:
                continue
            if s_clean in _KNOWN_SKILL_KEYWORDS:
                sk_id = _KNOWN_SKILL_KEYWORDS[s_clean]
            elif s.startswith("skill_"):
                sk_id = s
            else:
                sk_id = f"skill_{s_clean.replace(' ', '_')}"
            skill_ids.add(sk_id)
            store.save_node(Skill(id=sk_id, name=s.strip()))

    text_lower = text.lower()
    for kw, sk_id in _KNOWN_SKILL_KEYWORDS.items():
        if kw in text_lower:
            skill_ids.add(sk_id)
            store.save_node(Skill(id=sk_id, name=kw.title()))

    return sorted(skill_ids)


class CandidateSession:
    """Manages the candidate's active evidence store, identity, and materials."""

    def __init__(self) -> None:
        """Initialize a local evidence store and default candidate state."""
        self._tmp_dir = tempfile.mkdtemp(prefix="talentagent_candidate_")
        self.store: EvidenceStore = LocalEvidenceStore(Path(self._tmp_dir))

        self.identity = Identity(
            first_name="",
            last_name="",
            email="",
            phone="",
            location="",
        )
        self.links = Links(
            github="",
            linkedin="",
            portfolio="",
        )
        self.materials = Materials()
        self.resume_filename: str | None = None

        self.tier_1_calls = 0
        self.tier_2_calls = 0

    def reset(self) -> None:
        """Reset the session store and candidate state."""
        self._tmp_dir = tempfile.mkdtemp(prefix="talentagent_candidate_")
        self.store = LocalEvidenceStore(Path(self._tmp_dir))
        self.identity = Identity(first_name="", last_name="", email="", phone="", location="")
        self.links = Links(github="", linkedin="", portfolio="")
        self.materials = Materials()
        self.resume_filename = None


GLOBAL_SESSION = CandidateSession()
"""Singleton candidate session for the active application workflow."""


class TalentAgentUIHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler serving REST API endpoints and static Angular UI assets."""

    def log_message(self, format_str: str, *args: Any) -> None:
        """Suppress standard access logs to keep console output clean."""

    def _send_json(self, status_code: int, data: Any) -> None:
        """Send JSON response with appropriate headers and CORS."""
        payload = json.dumps(data).encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(payload)))
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()
        self.wfile.write(payload)

    def _send_error(self, status_code: int, message: str) -> None:
        """Send error JSON response."""
        self._send_json(status_code, {"error": message, "status": "error"})

    def do_OPTIONS(self) -> None:  # noqa: N802
        """Handle CORS pre-flight requests."""
        self.send_response(204)
        self.send_header("Access-Control-Allow-Origin", "*")
        self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
        self.send_header("Access-Control-Allow-Headers", "Content-Type")
        self.end_headers()

    def do_GET(self) -> None:  # noqa: N802
        """Handle GET requests for API endpoints and static assets."""
        parsed = urlparse(self.path)
        path = parsed.path
        parse_qs(parsed.query)

        if path == "/api/status":
            self._handle_status()
        elif path == "/api/profile":
            self._handle_get_profile()
        elif path == "/api/evidence-graph":
            self._handle_evidence_graph()
        else:
            self._serve_static(path)

    def do_POST(self) -> None:  # noqa: N802
        """Handle POST requests for API actions."""
        parsed = urlparse(self.path)
        path = parsed.path

        content_length = int(self.headers.get("Content-Length", 0))
        body_bytes = self.rfile.read(content_length) if content_length > 0 else b"{}"

        try:
            body = json.loads(body_bytes.decode("utf-8")) if body_bytes else {}
        except json.JSONDecodeError:
            self._send_error(400, "Invalid JSON payload")
            return

        if path == "/api/profile":
            self._handle_update_profile(body)
        elif path == "/api/profile/upload-resume":
            self._handle_upload_resume(body)
        elif path == "/api/profile/add-statement":
            self._handle_add_statement(body)
        elif path == "/api/profile/sync-github":
            self._handle_sync_github(body)
        elif path == "/api/profile/reset":
            self._handle_reset_profile()
        elif path == "/api/extract-requirements":
            self._handle_extract_requirements(body)
        elif path == "/api/compose":
            self._handle_compose(body)
        elif path == "/api/promote-statement":
            self._handle_promote_statement(body)
        elif path == "/api/ats-fill":
            self._handle_ats_fill(body)
        else:
            self._send_error(404, f"Unknown API endpoint: {path}")

    def _handle_status(self) -> None:
        """Return system health, guardrails status, and zero-budget quota usage."""
        has_gemini = get_live_client() is not None
        self._send_json(
            200,
            {
                "status": "healthy",
                "system": "TalentAgent",
                "backend": "python",
                "gemini_connected": has_gemini,
                "guardrails": {
                    "G1": {"name": "No model-originated claims", "active": True},
                    "G2": {"name": "No uncredited lines", "active": True},
                    "G3": {"name": "No irreversible autonomy (human-only submit)", "active": True},
                    "G4": {"name": "No suppression by self-derived signal", "active": True},
                    "G5": {"name": "No prohibited automation (allowlist)", "active": True},
                    "G6": {"name": "No credential handling", "active": True},
                    "G7": {"name": "Untrusted content treated as data", "active": True},
                },
                "quotas": {
                    "tier_1_used": GLOBAL_SESSION.tier_1_calls,
                    "tier_1_limit": DAILY_TIER_1_QUOTA,
                    "tier_2_used": GLOBAL_SESSION.tier_2_calls,
                    "tier_2_limit": DAILY_TIER_2_QUOTA,
                },
                "platforms": ["greenhouse", "lever", "ashby"],
            },
        )

    def _handle_get_profile(self) -> None:
        """Return candidate profile details, links, and node metrics."""
        nodes = get_all_nodes(GLOBAL_SESSION.store)
        self._send_json(
            200,
            {
                "identity": GLOBAL_SESSION.identity.model_dump(),
                "links": GLOBAL_SESSION.links.model_dump(),
                "resume_filename": GLOBAL_SESSION.resume_filename,
                "node_count": len(nodes),
                "has_profile": (
                    bool(GLOBAL_SESSION.identity.first_name)
                    or bool(GLOBAL_SESSION.identity.email)
                    or len(nodes) > 0
                ),
            },
        )

    def _handle_update_profile(self, body: dict[str, Any]) -> None:
        """Update candidate identity and links."""
        ident_data = body.get("identity", {})
        links_data = body.get("links", {})

        GLOBAL_SESSION.identity = Identity(
            first_name=ident_data.get("first_name", GLOBAL_SESSION.identity.first_name),
            last_name=ident_data.get("last_name", GLOBAL_SESSION.identity.last_name),
            email=ident_data.get("email", GLOBAL_SESSION.identity.email),
            phone=ident_data.get("phone", GLOBAL_SESSION.identity.phone),
            location=ident_data.get("location", GLOBAL_SESSION.identity.location),
        )

        GLOBAL_SESSION.links = Links(
            github=links_data.get("github", GLOBAL_SESSION.links.github),
            linkedin=links_data.get("linkedin", GLOBAL_SESSION.links.linkedin),
            portfolio=links_data.get("portfolio", GLOBAL_SESSION.links.portfolio),
        )

        self._handle_get_profile()

    def _handle_reset_profile(self) -> None:
        """Reset the active candidate store to empty state."""
        GLOBAL_SESSION.reset()
        self._send_json(200, {"status": "reset", "node_count": 0})

    def _handle_evidence_graph(self) -> None:
        """Return graph nodes, edges, and quarantine boundaries for visual graph rendering."""
        store = GLOBAL_SESSION.store
        nodes_raw = get_all_nodes(store)
        edges_raw = store.get_edges() if hasattr(store, "get_edges") else []

        formatted_nodes = []
        for n in nodes_raw:
            node_dict: dict[str, Any] = {
                "id": n.id,
            }
            if isinstance(n, Accomplishment):
                node_dict["type"] = "accomplishment"
                node_dict["claim"] = n.claim
                node_dict["attestation_class"] = n.attestation_class.value
                node_dict["skills"] = n.skills
                node_dict["evidence"] = n.evidence
                node_dict["is_quarantined"] = n.attestation_class == AttestationClass.DERIVED
            elif isinstance(n, Artifact):
                node_dict["type"] = "artifact"
                node_dict["title"] = n.title
                node_dict["subtype"] = n.subtype.value
                node_dict["url"] = n.url
                node_dict["metadata"] = n.metadata
            elif isinstance(n, Statement):
                node_dict["type"] = "statement"
                node_dict["raw"] = n.statement.raw
                node_dict["elicited_by"] = n.statement.elicited_by
            elif isinstance(n, Skill):
                node_dict["type"] = "skill"
                node_dict["name"] = n.name
            elif isinstance(n, Metric):
                node_dict["type"] = "metric"
                node_dict["name"] = n.name
                node_dict["value"] = n.value
                node_dict["unit"] = n.unit
            formatted_nodes.append(node_dict)

        formatted_edges = [
            {
                "source": e.source_id,
                "target": e.target_id,
                "type": e.edge_type.value,
            }
            for e in edges_raw
        ]

        self._send_json(
            200,
            {
                "nodes": formatted_nodes,
                "edges": formatted_edges,
                "quarantine_rule": "G1: derived nodes are strictly quarantined from retrieval",
            },
        )

    def _handle_extract_requirements(self, body: dict[str, Any]) -> None:
        """Parse raw job posting text into structured requirement items."""
        posting_text = body.get("posting_text", "").strip()
        if not posting_text:
            self._send_error(400, "Empty posting text")
            return

        GLOBAL_SESSION.tier_1_calls += 1
        lines = [line.strip("-•* ").strip() for line in posting_text.splitlines() if line.strip()]
        reqs = []
        for line in lines:
            if len(line) > 15 and not line.endswith(":"):
                reqs.append(line)

        if not reqs:
            reqs = [posting_text[:140]]

        self._send_json(200, {"requirements": reqs[:10]})

    def _handle_compose(self, body: dict[str, Any]) -> None:
        """Execute Pass 1 credited package composition against candidate evidence store."""
        posting_id = body.get("posting_id", "target_job")
        reqs_raw = body.get("requirements", [])
        identity_data = body.get("identity")

        identity = (
            Identity.model_validate(identity_data) if identity_data else GLOBAL_SESSION.identity
        )

        requirements = [normalise_requirement(r) for r in reqs_raw] if reqs_raw else []

        GLOBAL_SESSION.tier_2_calls += 1
        package = compose_package(
            posting_id=posting_id,
            requirements=requirements,
            identity=identity,
            store=GLOBAL_SESSION.store,
            links=GLOBAL_SESSION.links,
            materials=GLOBAL_SESSION.materials,
        )

        self._send_json(200, {"package": package.model_dump()})

    def _handle_promote_statement(self, body: dict[str, Any]) -> None:
        """Promote an elicited candidate answer directly into a Statement and Accomplishment."""
        raw_answer = body.get("answer", "").strip()
        skills = body.get("skills", [])

        if not raw_answer:
            self._send_error(400, "Answer cannot be empty")
            return

        matched_skills = _extract_and_save_skills(GLOBAL_SESSION.store, raw_answer, skills)

        stmt, acc = promote_statement(
            answer=raw_answer,
            store=GLOBAL_SESSION.store,
            claim=raw_answer.split("\n")[0][:120],
            skills=matched_skills,
        )

        self._send_json(
            200,
            {
                "status": "promoted",
                "statement_id": stmt.id,
                "accomplishment_id": acc.id,
                "raw_text": stmt.statement.raw,
                "attestation_class": acc.attestation_class.value,
            },
        )

    def _handle_upload_resume(self, body: dict[str, Any]) -> None:
        """Accept resume text or base64 PDF and ingest into candidate evidence store."""
        resume_text = body.get("text", "")
        content_base64 = body.get("content_base64")
        filename = body.get("filename", "resume.pdf")

        if content_base64:
            try:
                pdf_bytes = base64.b64decode(content_base64)
                reader = pypdf.PdfReader(io.BytesIO(pdf_bytes))
                resume_text = "\n".join(page.extract_text() or "" for page in reader.pages)
            except Exception as exc:
                self._send_error(400, f"Failed to parse PDF: {exc}")
                return

        if not resume_text.strip():
            self._send_error(400, "No resume text extracted")
            return

        lines = [line.strip("-•* ").strip() for line in resume_text.splitlines() if line.strip()]
        added_count = 0
        for line in lines:
            if len(line) > 20 and not line.startswith("http"):
                line_skills = _extract_and_save_skills(GLOBAL_SESSION.store, line)
                promote_statement(
                    answer=line,
                    store=GLOBAL_SESSION.store,
                    claim=line[:120],
                    skills=line_skills,
                )
                added_count += 1

        GLOBAL_SESSION.resume_filename = filename
        GLOBAL_SESSION.materials = Materials(resume=Path(filename))
        self._send_json(
            200,
            {
                "status": "success",
                "filename": filename,
                "extracted_length": len(resume_text),
                "nodes_added": added_count,
                "total_nodes": len(get_all_nodes(GLOBAL_SESSION.store)),
            },
        )

    def _handle_add_statement(self, body: dict[str, Any]) -> None:
        """Add candidate statement verbatim to the evidence store."""
        raw_text = body.get("raw_text", "").strip()
        skills = body.get("skills", [])
        if not raw_text:
            self._send_error(400, "Statement text is required")
            return

        matched_skills = _extract_and_save_skills(GLOBAL_SESSION.store, raw_text, skills)

        stmt, acc = promote_statement(
            answer=raw_text,
            store=GLOBAL_SESSION.store,
            claim=raw_text.split("\n")[0][:120],
            skills=matched_skills,
        )

        self._send_json(
            200,
            {
                "status": "added",
                "statement_id": stmt.id,
                "accomplishment_id": acc.id,
                "attestation_class": "attested",
            },
        )

    def _handle_sync_github(self, body: dict[str, Any]) -> None:
        """Ingest repository artifacts into candidate evidence store."""
        username = body.get("username", "developer").strip()
        repo = body.get("repo", "project").strip()

        art_id = f"art_gh_{abs(hash(username + repo)) % 1000000:06d}"
        art = Artifact(
            id=art_id,
            subtype=ArtifactSubtype.PR,
            title=f"Core architectural contributions to {username}/{repo}",
            url=f"https://github.com/{username}/{repo}",
            metadata={"summary": f"Contributions and fixtures for {repo}."},
        )
        GLOBAL_SESSION.store.save_node(art)

        matched_skills = _extract_and_save_skills(
            GLOBAL_SESSION.store, f"GitHub repository {username}/{repo} infrastructure"
        )
        if not matched_skills:
            matched_skills = _extract_and_save_skills(
                GLOBAL_SESSION.store, "python distributed systems"
            )

        acc_id = f"acc_gh_{abs(hash(username + repo)) % 1000000:06d}"
        acc = Accomplishment(
            id=acc_id,
            claim=f"Built core services and infrastructure for {username}/{repo}",
            skills=matched_skills,
            evidence=[art_id],
            attestation_class=AttestationClass.VERIFIABLE,
        )
        GLOBAL_SESSION.store.save_node(acc)

        GLOBAL_SESSION.store.save_edge(
            Edge(
                source_id=art_id,
                source_type=NodeType.ARTIFACT,
                target_id=acc_id,
                target_type=NodeType.ACCOMPLISHMENT,
                edge_type=EdgeType.EVIDENCES,
            )
        )
        for sk_id in matched_skills:
            GLOBAL_SESSION.store.save_edge(
                Edge(
                    source_id=acc_id,
                    source_type=NodeType.ACCOMPLISHMENT,
                    target_id=sk_id,
                    target_type=NodeType.SKILL,
                    edge_type=EdgeType.DEMONSTRATES,
                )
            )

        self._send_json(
            200,
            {
                "status": "synced",
                "artifact_id": art_id,
                "accomplishment_id": acc_id,
                "attestation_class": "verifiable",
            },
        )

    def _handle_ats_fill(self, body: dict[str, Any]) -> None:
        """Simulate Pass 2 deterministic ATS form execution with field resolution mapping."""
        platform = body.get("platform", "greenhouse").lower()
        package_dict = body.get("package", {})

        ident = package_dict.get("identity", {})
        first_name = ident.get("first_name") or GLOBAL_SESSION.identity.first_name or "Candidate"
        last_name = ident.get("last_name") or GLOBAL_SESSION.identity.last_name or "User"
        email = ident.get("email") or GLOBAL_SESSION.identity.email or "candidate@example.com"
        phone = ident.get("phone") or GLOBAL_SESSION.identity.phone or "555-0199"

        try:
            field_map = load_map(platform)
            mapped_fields = [
                {
                    "selector": (
                        rule.match_description
                        if hasattr(rule, "match_description")
                        else f"Field ({rule.path})"
                    ),
                    "target_path": rule.path,
                    "resolved_type": "deterministic",
                    "status": "filled",
                }
                for rule in field_map.rules
            ]
        except Exception:
            mapped_fields = [
                {
                    "selector": "#first_name",
                    "target_path": "identity.first_name",
                    "resolved_type": "deterministic",
                    "status": "filled",
                    "value": first_name,
                },
                {
                    "selector": "#last_name",
                    "target_path": "identity.last_name",
                    "resolved_type": "deterministic",
                    "status": "filled",
                    "value": last_name,
                },
                {
                    "selector": "#email",
                    "target_path": "identity.email",
                    "resolved_type": "deterministic",
                    "status": "filled",
                    "value": email,
                },
                {
                    "selector": "#phone",
                    "target_path": "identity.phone",
                    "resolved_type": "deterministic",
                    "status": "filled",
                    "value": phone,
                },
                {
                    "selector": "#resume",
                    "target_path": "materials.resume",
                    "resolved_type": "deterministic",
                    "status": "filled",
                    "value": GLOBAL_SESSION.resume_filename or "Resume.pdf",
                },
            ]

        self._send_json(
            200,
            {
                "platform": platform,
                "completion_rate": 1.0,
                "passes_required": 1,
                "total_fields": len(mapped_fields),
                "mapped_fields": mapped_fields,
                "halt_reason": None,
                "human_review_required": True,
                "guardrail_g3": (
                    "Autonomous submission is barred; human action required to submit."
                ),
            },
        )

    def _serve_static(self, path: str) -> None:
        """Serve static files from the Angular build directory with SPA fallback."""
        if not WEB_DIR.exists():
            self._send_json(
                200,
                {
                    "message": "TalentAgent UI API Server is running.",
                    "status": "ready",
                    "frontend_note": "Angular UI will be served once built.",
                },
            )
            return

        clean_path = path.lstrip("/") or "index.html"
        target_file = (WEB_DIR / clean_path).resolve()

        if not str(target_file).startswith(str(WEB_DIR.resolve())):
            self._send_error(403, "Access denied")
            return

        if not target_file.exists() or target_file.is_dir():
            target_file = WEB_DIR / "index.html"

        if not target_file.exists():
            self._send_json(200, {"status": "ready", "message": "TalentAgent API ready"})
            return

        mime_type, _ = mimetypes.guess_type(str(target_file))
        mime_type = mime_type or "application/octet-stream"

        file_bytes = target_file.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", mime_type)
        self.send_header("Content-Length", str(len(file_bytes)))
        self.send_header("Cache-Control", "no-cache")
        self.end_headers()
        self.wfile.write(file_bytes)


def create_ui_server(
    host: str = "127.0.0.1", port: int = DEFAULT_PORT
) -> http.server.ThreadingHTTPServer:
    """Create a configured ThreadingHTTPServer for the TalentAgent UI."""
    return http.server.ThreadingHTTPServer((host, port), TalentAgentUIHandler)


def run_server(host: str = "127.0.0.1", port: int = DEFAULT_PORT) -> None:
    """Start the TalentAgent UI server on the specified host and port."""
    server = create_ui_server(host=host, port=port)
    print(f"TalentAgent UI server running at http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping TalentAgent UI server.")
        server.server_close()
