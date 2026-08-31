"""Shared fixtures for the Pass 2 suite."""

from pathlib import Path

import pytest
from talentagent.ats.package import ApplicationPackage, Identity, Links, Materials

ATS_FIXTURES = Path(__file__).parent.parent / "fixtures" / "ats"


@pytest.fixture
def package(tmp_path: Path) -> ApplicationPackage:
    """A package with every field a Phase 1 map can reference populated."""
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
