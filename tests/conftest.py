"""Session-wide test configuration.

The zero-network fixture here is the primary control on the Gemini free-tier quota (ADR-0012):
recorded golden responses are only a saving if nothing in the suite can reach a live model. It is
also what makes the suite deterministic, which is the harder problem to notice going wrong.
"""

import socket
from collections.abc import Iterator
from pathlib import Path

import pytest
from talentagent.composer.package import ApplicationPackage, Identity, Links, Materials

ATS_FIXTURES = Path(__file__).parent / "fixtures" / "ats"
"""Where the offline ATS forms live. Shared so both the Pass 2 suite and the worker suite point at
one copy rather than each carrying its own path.
"""


class NetworkAccessDenied(RuntimeError):
    """Raised when a test attempts an outbound connection."""


def _deny(*_args: object, **_kwargs: object) -> None:
    """Stand in for socket.socket, refusing every outbound connection attempt."""
    raise NetworkAccessDenied(
        "This test attempted an outbound network connection. The suite makes zero API calls "
        "(ADR-0012): record a golden response with `python -m talentagent.models.record` and "
        "replay it, or mark the test `@pytest.mark.network` if it needs the emulator."
    )


@pytest.fixture(autouse=True)
def _no_network(request: pytest.FixtureRequest) -> Iterator[None]:
    """Refuse outbound connections unless the test is explicitly marked `network`."""
    if request.node.get_closest_marker("network"):
        yield
        return
    original = socket.socket
    socket.socket = _deny  # type: ignore[assignment,misc]
    try:
        yield
    finally:
        socket.socket = original  # type: ignore[misc]


@pytest.fixture(autouse=True)
def _no_live_model(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin the UI server's model client to None for every test.

    The server builds a live client at import when a `GEMINI_API_KEY` is present, so without
    this a developer with a key configured would run a different suite from CI. Tests that mean
    to exercise a model inject their own client (ADR-0012).
    """
    monkeypatch.setattr("talentagent.ui.server.MODEL_CLIENT", None)


@pytest.fixture
def package(tmp_path: Path) -> ApplicationPackage:
    """A package with every field a Phase 1 field map can reference populated."""
    resume = tmp_path / "resume.pdf"
    resume.write_bytes(b"%PDF-1.4 resume")
    cover = tmp_path / "cover.pdf"
    cover.write_bytes(b"%PDF-1.4 cover")
    return ApplicationPackage(
        posting_id="job_9a2",
        identity=Identity(
            first_name="Ada",
            last_name="Lovelace",
            email="ada@example.com",
            phone="+44 20 7946 0000",
            location="London",
            current_company="Analytical Engines",
        ),
        links=Links(
            linkedin="https://www.linkedin.com/in/example",
            github="https://github.com/example",
        ),
        materials=Materials(
            resume=resume, cover_letter=cover, cover_letter_text="A short cover letter."
        ),
    )


@pytest.fixture
def changed_form(tmp_path: Path) -> Path:
    """A Greenhouse form whose email field has become a select the package's value cannot satisfy.

    The DOM change ADR-0008 expects a map to notice rather than work around, shared by every test
    that pins what a halt does.
    """
    source = ATS_FIXTURES / "greenhouse" / "plain.html"
    changed = tmp_path / "plain.html"
    changed.write_text(
        source.read_text().replace(
            '<input type="email" id="email" name="job_application[email]" required>',
            '<select id="email" name="job_application[email]">'
            '<option value="a@example.com">a</option></select>',
        )
    )
    return changed
