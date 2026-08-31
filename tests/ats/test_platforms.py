"""Pins how a posting URL routes to a platform, and when two URLs are the same posting."""

import pytest
from talentagent.ats.platforms import UnsupportedPlatform, platform_for, same_posting


@pytest.mark.parametrize(
    ("url", "expected"),
    [
        ("https://boards.greenhouse.io/acme/jobs/1", "greenhouse"),
        ("https://job-boards.greenhouse.io/acme/jobs/1", "greenhouse"),
        ("https://jobs.lever.co/acme/abc", "lever"),
        ("https://jobs.ashbyhq.com/acme/xyz", "ashby"),
    ],
)
def test_every_targeted_host_routes_to_its_map(url: str, expected: str) -> None:
    """Both Greenhouse hosts route to the same map, since both serve the same postings."""
    assert platform_for(url) == expected


def test_a_host_with_no_map_is_refused() -> None:
    """The refusal explains the scope decision rather than only failing."""
    with pytest.raises(UnsupportedPlatform, match="ADR-0010"):
        platform_for("https://www.linkedin.com/jobs/view/1")


@pytest.mark.parametrize(
    ("one", "other"),
    [
        (
            "https://boards.greenhouse.io/acme/jobs/1",
            "https://job-boards.greenhouse.io/acme/jobs/1",
        ),
        ("https://jobs.lever.co/acme/abc", "https://jobs.lever.co/acme/abc/"),
        ("https://jobs.lever.co/acme/abc", "https://jobs.lever.co/acme/abc#apply"),
    ],
)
def test_a_redirect_within_one_platform_is_still_the_same_posting(one: str, other: str) -> None:
    """A Greenhouse host redirect, a trailing slash, or a fragment must not read as a submission."""
    assert same_posting(one, other)


@pytest.mark.parametrize(
    ("one", "other"),
    [
        (
            "https://boards.greenhouse.io/acme/jobs/1",
            "https://boards.greenhouse.io/acme/jobs/1/confirmation",
        ),
        ("https://jobs.lever.co/acme/abc", "https://jobs.ashbyhq.com/acme/abc"),
    ],
)
def test_navigating_elsewhere_is_not_the_same_posting(one: str, other: str) -> None:
    """A confirmation page is how a submission would show itself, so it must not compare equal."""
    assert not same_posting(one, other)
