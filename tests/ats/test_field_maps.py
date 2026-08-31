"""Pins the three platform maps against the fixture manifests (issue #13).

The manifest is the contract: every field in a fixture is either given a package path or marked
unmapped, and this suite asserts the map agrees with it field for field. A field present in a
fixture and absent from its manifest fails here, so a fixture refresh cannot quietly add a field
nobody decided about.
"""

from pathlib import Path

import pytest
import yaml
from talentagent.ats.fieldmap import MissReason, load_map
from talentagent.ats.offline import OfflineHtmlPage
from talentagent.ats.package import ApplicationPackage
from talentagent.ats.resolver import resolve

from tests.ats.conftest import ATS_FIXTURES

PLATFORMS = ("greenhouse", "lever", "ashby")


def _manifest(platform: str) -> dict[str, dict[str, list[dict[str, object]]]]:
    """Load one platform's manifest."""
    loaded = yaml.safe_load((ATS_FIXTURES / platform / "manifest.yaml").read_text())
    return dict(loaded["fixtures"])


def _cases() -> list[tuple[str, str]]:
    """Return every (platform, fixture) pair the manifests declare."""
    return [(platform, name) for platform in PLATFORMS for name in _manifest(platform)]


@pytest.mark.parametrize(("platform", "fixture"), _cases(), ids=lambda v: str(v))
def test_every_fixture_field_is_accounted_for_in_its_manifest(platform: str, fixture: str) -> None:
    """The manifest enumerates exactly the fields the fixture contains, in both directions."""
    page = OfflineHtmlPage(ATS_FIXTURES / platform / fixture)
    in_page = {f.name for f in page.fields()}
    declared = {str(entry["name"]) for entry in _manifest(platform)[fixture]["fields"]}
    assert in_page == declared


@pytest.mark.parametrize(("platform", "fixture"), _cases(), ids=lambda v: str(v))
def test_the_map_agrees_with_the_manifest_field_for_field(
    platform: str, fixture: str, package: ApplicationPackage
) -> None:
    """Every field the manifest gives a path resolves; every field it marks unmapped misses."""
    page = OfflineHtmlPage(ATS_FIXTURES / platform / fixture)
    result = resolve(page.fields(), load_map(platform), package, include_hidden=True)

    resolved = {r.name: r.path for r in result.resolved}
    missed = {m.name: m.reason for m in result.missed}

    for entry in _manifest(platform)[fixture]["fields"]:
        name = str(entry["name"])
        if entry.get("unmapped"):
            assert name in missed, f"{name} should not have resolved"
        else:
            assert resolved.get(name) == entry["path"], f"{name} resolved to the wrong path"


@pytest.mark.parametrize(("platform", "fixture"), _cases(), ids=lambda v: str(v))
def test_declined_fields_are_declined_by_the_map_not_merely_unmatched(
    platform: str, fixture: str, package: ApplicationPackage
) -> None:
    """A demographic question is refused deliberately, so the fallback cannot answer it either."""
    page = OfflineHtmlPage(ATS_FIXTURES / platform / fixture)
    result = resolve(page.fields(), load_map(platform), package, include_hidden=True)
    missed = {m.name: m.reason for m in result.missed}

    for entry in _manifest(platform)[fixture]["fields"]:
        if entry.get("declined"):
            name = str(entry["name"])
            assert missed[name] is MissReason.DECLARED_UNMAPPED, (
                f"{name} must be declined by a rule, not left unmatched"
            )


@pytest.mark.parametrize("platform", PLATFORMS)
def test_standard_fields_resolve_completely_on_every_platform(
    platform: str, package: ApplicationPackage
) -> None:
    """The plain and upload fixtures contain only standard fields, so the map covers them fully."""
    for fixture in ("plain.html", "file-upload.html"):
        page = OfflineHtmlPage(ATS_FIXTURES / platform / fixture)
        result = resolve(page.fields(), load_map(platform), package)
        assert not result.missed, f"{platform}/{fixture} left {[m.name for m in result.missed]}"


@pytest.mark.parametrize("platform", PLATFORMS)
def test_adding_a_field_needs_no_resolver_change(platform: str, tmp_path: Path) -> None:
    """A map is data: appending a rule changes behaviour with no code change."""
    original = (Path("talentagent/ats/maps") / f"{platform}.yaml").read_text()
    extended = tmp_path / f"{platform}.yaml"
    extended.write_text(
        original + '  - match: {name: "brand_new_field"}\n    path: links.portfolio\n'
    )
    assert len(load_map(platform, root=tmp_path).rules) == len(load_map(platform).rules) + 1
