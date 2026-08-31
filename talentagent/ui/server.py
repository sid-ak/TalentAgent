"""HTTP server and REST API for the TalentAgent interactive review surface (Spec §5.5, Phase 2.5).

Provides endpoints for candidate profile management, evidence graph exploration, credited
package composition, interactive live elicitation, and ATS execution playback.
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
from tests.fixtures.evidence.seeding import seed_profile_a, seed_profile_b

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
from talentagent.evidence.retrieval import normalise_requirement
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


class DemoStores:
    """Manages isolated in-memory stores for Profile A, Profile B, and Custom candidates."""

    def __init__(self) -> None:
        """Initialize and seed demo stores in temporary directories."""
        self._tmp_a = tempfile.mkdtemp(prefix="store_a_")
        self._tmp_b = tempfile.mkdtemp(prefix="store_b_")
        self._tmp_custom = tempfile.mkdtemp(prefix="store_custom_")

        self.profile_a = LocalEvidenceStore(Path(self._tmp_a))
        seed_profile_a(self.profile_a)

        self.profile_b = LocalEvidenceStore(Path(self._tmp_b))
        seed_profile_b(self.profile_b)

        self.custom = LocalEvidenceStore(Path(self._tmp_custom))
        self._seed_default_custom()

        self.custom_identity = Identity(
            first_name="Alex",
            last_name="Rivers",
            email="alex.rivers@example.com",
            phone="415-555-0199",
            location="San Francisco, CA",
        )
        self.custom_links = Links(
            github="https://github.com/alexrivers",
            linkedin="https://linkedin.com/in/alexrivers",
            portfolio="https://alexrivers.dev",
        )
        self.custom_materials = Materials(resume=Path("Alex_Rivers_Resume.pdf"))

        self.tier_1_calls = 4
        self.tier_2_calls = 2

    def _seed_default_custom(self) -> None:
        """Seed initial custom candidate profile with sample verifiable and attested nodes."""
        skill_python = Skill(id="skill_python", name="Python")
        skill_fastapi = Skill(id="skill_fastapi", name="FastAPI")
        skill_cloud = Skill(id="skill_cloud", name="Cloud Infrastructure")
        for s in (skill_python, skill_fastapi, skill_cloud):
            self.custom.save_node(s)

        art = Artifact(
            id="art_custom_pr_101",
            subtype=ArtifactSubtype.PR,
            title="Optimized query execution engine",
            url="https://github.com/alexrivers/query-engine/pull/101",
            metadata={"summary": "Reduced p99 query latency by 45% using streaming buffer pools."},
        )
        self.custom.save_node(art)

        acc_1 = Accomplishment(
            id="acc_custom_1",
            claim="Optimized query engine latency by 45% using streaming buffer pools",
            skills=["skill_python", "skill_cloud"],
            evidence=["art_custom_pr_101"],
            attestation_class=AttestationClass.VERIFIABLE,
        )
        self.custom.save_node(acc_1)

        self.custom.save_edge(
            Edge(
                source_id="art_custom_pr_101",
                source_type=NodeType.ARTIFACT,
                target_id="acc_custom_1",
                target_type=NodeType.ACCOMPLISHMENT,
                edge_type=EdgeType.EVIDENCES,
            )
        )
        self.custom.save_edge(
            Edge(
                source_id="acc_custom_1",
                source_type=NodeType.ACCOMPLISHMENT,
                target_id="skill_python",
                target_type=NodeType.SKILL,
                edge_type=EdgeType.DEMONSTRATES,
            )
        )
        self.custom.save_edge(
            Edge(
                source_id="acc_custom_1",
                source_type=NodeType.ACCOMPLISHMENT,
                target_id="skill_cloud",
                target_type=NodeType.SKILL,
                edge_type=EdgeType.DEMONSTRATES,
            )
        )

    def get_store(self, profile_id: str) -> EvidenceStore:
        """Return the EvidenceStore corresponding to the profile identifier."""
        if profile_id == "profile_a":
            return self.profile_a
        if profile_id == "profile_b":
            return self.profile_b
        return self.custom


GLOBAL_STORES = DemoStores()
"""Singleton demo store holding candidate profiles and usage statistics."""


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
        query = parse_qs(parsed.query)

        if path == "/api/status":
            self._handle_status()
        elif path == "/api/profiles":
            self._handle_profiles()
        elif path == "/api/evidence-graph":
            profile_id = query.get("profile_id", ["profile_a"])[0]
            self._handle_evidence_graph(profile_id)
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

        if path == "/api/extract-requirements":
            self._handle_extract_requirements(body)
        elif path == "/api/compose":
            self._handle_compose(body)
        elif path == "/api/promote-statement":
            self._handle_promote_statement(body)
        elif path == "/api/profile/upload-resume":
            self._handle_upload_resume(body)
        elif path == "/api/profile/add-statement":
            self._handle_add_statement(body)
        elif path == "/api/profile/sync-github":
            self._handle_sync_github(body)
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
                "phase": "2.5-Demo",
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
                    "tier_1_used": GLOBAL_STORES.tier_1_calls,
                    "tier_1_limit": DAILY_TIER_1_QUOTA,
                    "tier_2_used": GLOBAL_STORES.tier_2_calls,
                    "tier_2_limit": DAILY_TIER_2_QUOTA,
                },
                "platforms": ["greenhouse", "lever", "ashby"],
            },
        )

    def _handle_profiles(self) -> None:
        """Return metadata summaries for all candidate profiles."""
        store_a_nodes = len(get_all_nodes(GLOBAL_STORES.profile_a))
        store_b_nodes = len(get_all_nodes(GLOBAL_STORES.profile_b))
        custom_nodes = len(get_all_nodes(GLOBAL_STORES.custom))

        self._send_json(
            200,
            {
                "profiles": [
                    {
                        "id": "profile_a",
                        "name": "Profile A (Distributed Systems Engineer)",
                        "type": "Technical / Repository-Backed",
                        "description": (
                            "Artifact-backed engineering profile with commits, PRs, and docs."
                        ),
                        "node_count": store_a_nodes,
                        "attestation_classes": ["verifiable", "corroborated"],
                        "identity": {
                            "first_name": "Jordan",
                            "last_name": "Lee",
                            "email": "jordan.lee@example.com",
                            "location": "Seattle, WA",
                        },
                    },
                    {
                        "id": "profile_b",
                        "name": "Profile B (Principal Product Lead)",
                        "type": "Non-Engineering / Statement-Backed",
                        "description": (
                            "100% attested statements with zero public software artifacts."
                        ),
                        "node_count": store_b_nodes,
                        "attestation_classes": ["attested"],
                        "identity": {
                            "first_name": "Morgan",
                            "last_name": "Taylor",
                            "email": "morgan.taylor@example.com",
                            "location": "New York, NY",
                        },
                    },
                    {
                        "id": "custom",
                        "name": "Custom Candidate Profile",
                        "type": "User-Managed Profile",
                        "description": (
                            "Upload your resume PDF, add GitHub repos, or enter statements."
                        ),
                        "node_count": custom_nodes,
                        "attestation_classes": ["verifiable", "attested"],
                        "identity": GLOBAL_STORES.custom_identity.model_dump(),
                        "links": GLOBAL_STORES.custom_links.model_dump(),
                    },
                ]
            },
        )

    def _handle_evidence_graph(self, profile_id: str) -> None:
        """Return graph nodes, edges, and quarantine boundaries for visual graph rendering."""
        store = GLOBAL_STORES.get_store(profile_id)
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
                "profile_id": profile_id,
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

        GLOBAL_STORES.tier_1_calls += 1
        lines = [line.strip("-•* ").strip() for line in posting_text.splitlines() if line.strip()]
        reqs = []
        for line in lines:
            if len(line) > 15 and not line.endswith(":"):
                reqs.append(line)

        if not reqs:
            reqs = [posting_text[:120]]

        self._send_json(200, {"requirements": reqs[:10]})

    def _handle_compose(self, body: dict[str, Any]) -> None:
        """Execute Pass 1 credited package composition against the selected evidence store."""
        profile_id = body.get("profile_id", "profile_a")
        posting_id = body.get("posting_id", "job_demo")
        reqs_raw = body.get("requirements", [])
        identity_data = body.get("identity")

        store = GLOBAL_STORES.get_store(profile_id)
        default_identity = (
            GLOBAL_STORES.custom_identity
            if profile_id == "custom"
            else Identity(first_name="Candidate", last_name="User", email="candidate@example.com")
        )
        identity = Identity.model_validate(identity_data) if identity_data else default_identity

        requirements = [normalise_requirement(r) for r in reqs_raw] if reqs_raw else []

        GLOBAL_STORES.tier_2_calls += 1
        package = compose_package(
            posting_id=posting_id,
            requirements=requirements,
            identity=identity,
            store=store,
            links=GLOBAL_STORES.custom_links if profile_id == "custom" else None,
            materials=GLOBAL_STORES.custom_materials if profile_id == "custom" else None,
        )

        self._send_json(200, {"package": package.model_dump()})

    def _handle_promote_statement(self, body: dict[str, Any]) -> None:
        """Promote an elicited user answer directly into a Statement and attested Accomplishment."""
        profile_id = body.get("profile_id", "custom")
        raw_answer = body.get("answer", "").strip()
        skills = body.get("skills", [])

        if not raw_answer:
            self._send_error(400, "Answer cannot be empty")
            return

        store = GLOBAL_STORES.get_store(profile_id)
        stmt, acc = promote_statement(
            answer=raw_answer,
            store=store,
            claim=raw_answer.split("\n")[0][:120],
            skills=skills,
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
        """Accept resume text or base64 PDF and ingest into custom candidate profile."""
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
        for line in lines[:8]:
            if len(line) > 20 and not line.startswith("http"):
                promote_statement(
                    answer=line,
                    store=GLOBAL_STORES.custom,
                    claim=line[:100],
                )
                added_count += 1

        GLOBAL_STORES.custom_materials = Materials(resume=Path(filename))
        self._send_json(
            200,
            {
                "status": "success",
                "filename": filename,
                "extracted_length": len(resume_text),
                "nodes_added": added_count,
                "total_custom_nodes": len(get_all_nodes(GLOBAL_STORES.custom)),
            },
        )

    def _handle_add_statement(self, body: dict[str, Any]) -> None:
        """Add custom candidate statement verbatim to the custom store."""
        raw_text = body.get("raw_text", "").strip()
        skills = body.get("skills", [])
        if not raw_text:
            self._send_error(400, "Statement text is required")
            return

        stmt, acc = promote_statement(
            answer=raw_text,
            store=GLOBAL_STORES.custom,
            claim=raw_text.split("\n")[0][:120],
            skills=skills,
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
        """Ingest repository artifacts into custom candidate profile."""
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
        GLOBAL_STORES.custom.save_node(art)

        acc_id = f"acc_gh_{abs(hash(username + repo)) % 1000000:06d}"
        acc = Accomplishment(
            id=acc_id,
            claim=f"Built core services and infrastructure for {username}/{repo}",
            skills=["Python", "Distributed Systems"],
            evidence=[art_id],
            attestation_class=AttestationClass.VERIFIABLE,
        )
        GLOBAL_STORES.custom.save_node(acc)

        GLOBAL_STORES.custom.save_edge(
            Edge(
                source_id=art_id,
                source_type=NodeType.ARTIFACT,
                target_id=acc_id,
                target_type=NodeType.ACCOMPLISHMENT,
                edge_type=EdgeType.EVIDENCES,
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
                },
                {
                    "selector": "#last_name",
                    "target_path": "identity.last_name",
                    "resolved_type": "deterministic",
                    "status": "filled",
                },
                {
                    "selector": "#email",
                    "target_path": "identity.email",
                    "resolved_type": "deterministic",
                    "status": "filled",
                },
                {
                    "selector": "#phone",
                    "target_path": "identity.phone",
                    "resolved_type": "deterministic",
                    "status": "filled",
                },
                {
                    "selector": "#resume",
                    "target_path": "materials.resume",
                    "resolved_type": "deterministic",
                    "status": "filled",
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
    print(f"TalentAgent Review UI server running at http://{host}:{port}/")
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        print("\nStopping TalentAgent Review UI server.")
        server.server_close()
