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
import os
import tempfile
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

import pypdf

from talentagent.agent.loop import extract_requirements, run_agent
from talentagent.ats.executor import fill_form
from talentagent.ats.fieldmap import load_map
from talentagent.ats.halt import HaltedRun
from talentagent.ats.offline import OfflineHtmlPage
from talentagent.ats.platforms import PLATFORM_BY_HOST
from talentagent.composer.compose import compose_package
from talentagent.composer.package import ApplicationPackage, Identity, Links, Materials
from talentagent.evidence.elicitation import promote_statement
from talentagent.evidence.graph import (
    Accomplishment,
    Artifact,
    AttestationClass,
    Metric,
    Skill,
    Statement,
)
from talentagent.evidence.retrieval import _KNOWN_SKILL_KEYWORDS, normalise_requirement
from talentagent.evidence.store import EvidenceStore, LocalEvidenceStore
from talentagent.models.client import Tier
from talentagent.models.live import TIER_MODELS, build_live_client

DEFAULT_PORT = 8080
"""Default HTTP port for the UI review server."""

GUARDRAIL_STATUS: dict[str, dict[str, str]] = {
    "G1": {"name": "No model-originated claims", "status": "enforced"},
    "G2": {"name": "No uncredited lines", "status": "enforced"},
    "G3": {"name": "No irreversible autonomy; submit is human-only", "status": "enforced"},
    "G4": {"name": "No suppression by self-derived signal", "status": "pending"},
    "G5": {"name": "No prohibited automation", "status": "enforced"},
    "G6": {"name": "No credential handling", "status": "vacuous"},
    "G7": {"name": "Untrusted content treated as data", "status": "enforced"},
}
"""What each guardrail's enforcement actually amounts to today (Spec §10).

`enforced` means a mechanism exists and a test fails when it is removed. `pending` means the
mechanism has not been built: G4's test is an `xfail` reading "not yet enforced", and reporting it
as active was the endpoint contradicting its own suite. `vacuous` means the invariant holds only
because there is nothing yet to violate it — G6 is checked by scanning tool names in a registry no
production path calls.
"""

ATS_PLATFORMS = frozenset(PLATFORM_BY_HOST.values())
"""The ATS platforms with a field map, taken from the host table so the two cannot diverge."""

ATS_FIXTURE_ROOT = Path(
    os.environ.get(
        "TALENTAGENT_ATS_FIXTURES",
        Path(__file__).resolve().parent.parent.parent / "tests" / "fixtures" / "ats",
    )
)
"""Where the demo's fillable forms live.

Pass 2 runs against the same offline forms the Spike A gate is measured on, rather than a copy —
a second set would drift from the one the gate reports, and then the demo and the number would
be describing different things.
"""

MODEL_CLIENT = build_live_client()
"""The live Gemini client, or None when no API key is configured.

Built once at import: the whole surface either has a model or reports that it does not, and
every handler reads the same answer.
"""

WEB_DIR = Path(
    os.environ.get("TALENTAGENT_WEB_DIR", Path(__file__).resolve().parent.parent.parent / "web")
)
"""Path to the static review surface served alongside the API.

Overridable by `TALENTAGENT_WEB_DIR`, because the default is derived from this file's position in
the source tree and stops being right the moment the package is installed rather than run in
place — which is exactly what happens inside a container image.
"""


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


def _session_package() -> ApplicationPackage:
    """Build a package from the session's identity alone, for a form-fill with no composition.

    Pass 2 fills the identity, links, and materials a field map names; the credited bullets are
    not form fields. So a caller that wants to watch the form fill without composing first gets a
    package carrying exactly what the map can reference, and nothing invented to pad it out.
    """
    materials = GLOBAL_SESSION.materials
    if materials.resume is None or not Path(materials.resume).exists():
        placeholder = Path(tempfile.mkdtemp(prefix="talentagent_resume_")) / "resume.pdf"
        placeholder.write_bytes(b"%PDF-1.4 placeholder resume")
        materials = Materials(resume=placeholder)

    return ApplicationPackage(
        posting_id="demo_posting",
        identity=GLOBAL_SESSION.identity,
        links=GLOBAL_SESSION.links,
        materials=materials,
    )


class TalentAgentUIHandler(http.server.BaseHTTPRequestHandler):
    """HTTP request handler serving REST API endpoints and the static review surface."""

    protocol_version = "HTTP/1.1"
    """Keep connections alive between requests.

    Every response here sets `Content-Length`, which is what HTTP/1.1 needs to find the end of a
    body. Under the 1.0 default a browser reopens a connection per call, and an agent run — which
    is several seconds of model calls — can be left waiting on one that was already closed.
    """

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
        elif path == "/api/profile/reset":
            self._handle_reset_profile()
        elif path == "/api/agent/run":
            self._handle_agent_run(body)
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
        quotas = (
            MODEL_CLIENT.ledger.report()
            if MODEL_CLIENT is not None
            else {t.value: {"used": 0, "limit": t.daily_limit} for t in Tier}
        )
        self._send_json(
            200,
            {
                "status": "healthy",
                "system": "TalentAgent",
                "backend": "python",
                "gemini_connected": MODEL_CLIENT is not None,
                "models": {
                    "tier_1": TIER_MODELS[Tier.ONE][0],
                    "tier_2": TIER_MODELS[Tier.TWO][0],
                },
                "guardrails": GUARDRAIL_STATUS,
                "quotas": quotas,
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
        """Extract structured requirements from a posting via the tier-1 model."""
        posting_text = body.get("posting_text", "").strip()
        if not posting_text:
            self._send_error(400, "Empty posting text")
            return

        requirements, used_model = extract_requirements(posting_text, MODEL_CLIENT)
        self._send_json(
            200,
            {
                "requirements": [r.text for r in requirements],
                "used_model": used_model,
            },
        )

    def _handle_agent_run(self, body: dict[str, Any]) -> None:
        """Run the agent loop over a posting and return its trace, package, and open gaps."""
        posting_text = body.get("posting_text", "").strip()
        if not posting_text:
            self._send_error(400, "Empty posting text")
            return

        if not get_all_nodes(GLOBAL_SESSION.store):
            self._send_error(400, "No evidence yet. Add your experience before running the agent.")
            return

        run = run_agent(
            posting_text=posting_text,
            store=GLOBAL_SESSION.store,
            identity=GLOBAL_SESSION.identity,
            links=GLOBAL_SESSION.links,
            materials=GLOBAL_SESSION.materials,
            model_client=MODEL_CLIENT,
            posting_id=body.get("posting_id", "target_posting"),
        )
        self._send_json(200, json.loads(run.model_dump_json()))

    def _handle_compose(self, body: dict[str, Any]) -> None:
        """Execute Pass 1 credited package composition against candidate evidence store."""
        posting_id = body.get("posting_id", "target_job")
        reqs_raw = body.get("requirements", [])
        identity_data = body.get("identity")

        identity = (
            Identity.model_validate(identity_data) if identity_data else GLOBAL_SESSION.identity
        )

        requirements = [normalise_requirement(r) for r in reqs_raw] if reqs_raw else []

        package = compose_package(
            posting_id=posting_id,
            requirements=requirements,
            identity=identity,
            store=GLOBAL_SESSION.store,
            links=GLOBAL_SESSION.links,
            materials=GLOBAL_SESSION.materials,
            model_client=MODEL_CLIENT,
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

    def _handle_ats_fill(self, body: dict[str, Any]) -> None:
        """Run Pass 2 against a fixture form and report the completion it actually measured."""
        platform = str(body.get("platform", "greenhouse")).lower()
        if platform not in ATS_PLATFORMS:
            self._send_error(400, f"Unknown platform {platform!r}")
            return

        form = ATS_FIXTURE_ROOT / platform / "plain.html"
        if not form.exists():
            self._send_error(503, "Fixture forms are not present in this deployment")
            return

        package_data = body.get("package")
        try:
            package = (
                ApplicationPackage.model_validate(package_data)
                if package_data
                else _session_package()
            )
        except ValueError as exc:
            self._send_error(400, f"Could not read the application package: {exc}")
            return

        page = OfflineHtmlPage(form)
        try:
            result = fill_form(page, load_map(platform), package)
            halted = None
        except HaltedRun as exc:
            result = exc.partial
            halted = str(exc)

        sources = result.log.sources()
        self._send_json(
            200,
            {
                "platform": platform,
                "form": f"{platform}/plain.html",
                "completion_rate": round(result.completion.rate, 3),
                "deterministic_share": round(result.completion.deterministic_share, 3),
                "passes": result.passes,
                "filled_fields": [
                    {"name": value.name, "value": value.value, "source": sources.get(value.name)}
                    for value in result.log.values
                ],
                "outstanding": [missed.name for missed in result.outstanding],
                "halted": halted,
                "submitted": result.submitted,
            },
        )

    def _serve_static(self, path: str) -> None:
        """Serve static files from the web directory with SPA fallback."""
        if not WEB_DIR.exists():
            self._send_json(
                200,
                {
                    "message": "TalentAgent UI API Server is running.",
                    "status": "ready",
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
