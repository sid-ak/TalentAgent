"""Pins that no fixture carries personal data or reaches the network (issue #8).

The repository is public so that Actions minutes stay unlimited (Architecture 6.4), which makes
this a publication check rather than a tidiness one. It runs as a test rather than a pre-commit
hook so it cannot be skipped.
"""

import re
from pathlib import Path

import pytest

FIXTURE_ROOT = Path(__file__).parent

_EMAIL = re.compile(r"[\w.+-]+@(?!example\.(com|org)\b|test\b)[\w-]+\.[a-z]{2,}", re.I)
"""Addresses that are reserved for documentation are fine; anything else that looks like a real
mailbox is not.
"""
_PHONE = re.compile(r"(?<!\d)(?!(?:19|20)\d{2}-\d{2}-\d{2})(\+?\d[\d\-\s().]{8,}\d)(?!\d)")
"""Phone number pattern matching formatted numbers while exempting ISO date stamps."""
_SCRIPTS = re.compile(r"<script\b", re.I)
_REMOTE_ASSET = re.compile(r'(src|href)\s*=\s*["\']https?://', re.I)


def _fixture_files() -> list[Path]:
    """Return every fixture file the hygiene rules apply to."""
    return sorted(p for p in FIXTURE_ROOT.rglob("*") if p.suffix in {".html", ".yaml", ".json"})


def test_there_are_fixtures_to_check() -> None:
    """Guards against the scan silently passing because it found nothing."""
    assert len(_fixture_files()) >= 12


@pytest.mark.parametrize("path", _fixture_files(), ids=lambda p: str(p.name))
def test_no_personal_data_in_fixtures(path: Path) -> None:
    """No fixture contains a real-looking email address or phone number."""
    text = path.read_text()
    assert not _EMAIL.search(text), f"{path} contains what looks like a real email address"
    assert not _PHONE.search(text), f"{path} contains what looks like a phone number"


@pytest.mark.parametrize(
    "path", [p for p in _fixture_files() if p.suffix == ".html"], ids=lambda p: str(p.name)
)
def test_fixtures_render_without_the_network(path: Path) -> None:
    """No fixture carries a script or a remote asset, so it renders with the network disabled."""
    text = path.read_text()
    assert not _SCRIPTS.search(text), f"{path} carries a script; fixtures must render offline"
    assert not _REMOTE_ASSET.search(text), f"{path} references a remote asset"
