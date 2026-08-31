"""Pins the field-map schema and the resolver's miss reporting (issue #12)."""

from pathlib import Path

import pytest
from talentagent.ats.fieldmap import (
    FieldMap,
    FieldMapError,
    FieldRule,
    MissReason,
    Strategy,
    load_map,
    normalise,
)
from talentagent.ats.page import FormField
from talentagent.ats.resolver import resolve
from talentagent.composer.package import ApplicationPackage


def _write_map(path: Path, body: str) -> Path:
    """Write a map file and return its directory, so load_map can find it by platform name."""
    path.write_text(body)
    return path.parent


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("Email *", "email"),
        ("Email  ✱", "email"),
        ("  First   Name  ", "first name"),
        ("Resume/CV (required)", "resume/cv"),
    ],
)
def test_labels_normalise_past_required_decoration(raw: str, expected: str) -> None:
    """A map keying on the label a human reads still matches the decorated rendering."""
    assert normalise(raw) == expected


def test_name_takes_precedence_over_label() -> None:
    """The precedence order is name, then label, then aria, and it is declaration order."""
    rule = FieldRule(match={Strategy.NAME: "email", Strategy.LABEL: "Email"}, path="identity.email")
    assert rule.matches("email", None, None)
    assert rule.matches("something_else", "Email", None)


def test_a_rule_survives_a_name_change_when_it_also_declares_a_label() -> None:
    """A cosmetic DOM change on one identity does not break a map that declares two."""
    rule = FieldRule(
        match={Strategy.NAME: "job_application[email]", Strategy.LABEL: "Email"},
        path="identity.email",
    )
    assert rule.matches("job_application[email_v2]", "Email *", None), "label must still resolve it"
    assert rule.matches("job_application[email]", "Contact address", None), "name must still work"


def test_aria_resolves_a_control_with_no_visible_label() -> None:
    """Ashby labels several built-in controls with nothing but aria-label."""
    rule = FieldRule(match={Strategy.ARIA: "Phone"}, path="identity.phone")
    assert rule.matches("_systemfield_phone", None, "Phone")


def test_a_malformed_map_fails_at_load(tmp_path: Path) -> None:
    """A bad map fails when it is read, not part-way through filling a live form."""
    root = _write_map(tmp_path / "broken.yaml", "platform: broken\nrules:\n  - {path: a.b}\n")
    with pytest.raises(FieldMapError, match="at least one identity strategy"):
        load_map("broken", root=root)


def test_a_rule_declaring_both_path_and_unmapped_is_refused(tmp_path: Path) -> None:
    """Exactly one of the two, so 'unmapped' cannot quietly coexist with a path that wins."""
    root = _write_map(
        tmp_path / "broken.yaml",
        "platform: broken\nrules:\n  - match: {name: x}\n    path: identity.email\n"
        "    unmapped: true\n",
    )
    with pytest.raises(FieldMapError, match="exactly one"):
        load_map("broken", root=root)


def test_a_missing_map_names_the_platform(tmp_path: Path) -> None:
    """Asking for a platform with no map is a clear error rather than an empty map."""
    with pytest.raises(FieldMapError, match="nosuch"):
        load_map("nosuch", root=tmp_path)


def test_an_unmatched_field_is_a_typed_miss_not_an_exception(
    package: ApplicationPackage,
) -> None:
    """The resolver never raises on a miss: the completion figure is built from the reasons."""
    field_map = FieldMap(
        "test", (FieldRule(match={Strategy.NAME: "email"}, path="identity.email"),)
    )
    fields = (
        FormField(name="email", kind="email", label="Email"),
        FormField(name="answers[3]", kind="text", label="Tell us about yourself"),
    )
    result = resolve(fields, field_map, package)
    assert [r.name for r in result.resolved] == ["email"]
    assert result.missed[0].reason is MissReason.NO_RULE
    assert result.total == 2


def test_the_four_miss_reasons_are_reported_separately(package: ApplicationPackage) -> None:
    """Declined, unmatched, empty, and not-yet-revealed are four different things."""
    field_map = FieldMap(
        "test",
        (
            FieldRule(match={Strategy.NAME: "eeo"}, unmapped=True, note="demographic question"),
            FieldRule(match={Strategy.NAME: "portfolio"}, path="links.portfolio"),
            FieldRule(match={Strategy.NAME: "later"}, path="identity.email"),
        ),
    )
    fields = (
        FormField(name="eeo", kind="select", label="Race/Ethnicity"),
        FormField(name="portfolio", kind="url", label="Portfolio"),
        FormField(name="unknown", kind="text", label="Why us?"),
        FormField(name="later", kind="text", label="Follow-up", visible=False),
    )
    result = resolve(fields, field_map, package)
    reasons = {m.name: m.reason for m in result.missed}
    assert reasons == {
        "eeo": MissReason.DECLARED_UNMAPPED,
        "portfolio": MissReason.NO_VALUE,
        "unknown": MissReason.NO_RULE,
        "later": MissReason.NOT_VISIBLE,
    }


def test_only_unmatched_fields_are_eligible_for_the_fallback(
    package: ApplicationPackage,
) -> None:
    """A field the map deliberately declined stays declined; the model does not get a second go."""
    field_map = FieldMap(
        "test",
        (FieldRule(match={Strategy.NAME: "eeo"}, unmapped=True, note="demographic question"),),
    )
    fields = (
        FormField(name="eeo", kind="select", label="Gender"),
        FormField(name="q_0", kind="text", label="Years of Kubernetes?"),
    )
    result = resolve(fields, field_map, package)
    assert [m.name for m in result.fallback_candidates] == ["q_0"]


def test_a_map_path_that_does_not_exist_fails_loudly(package: ApplicationPackage) -> None:
    """A typo in a map raises rather than filling the field with nothing."""
    field_map = FieldMap("test", (FieldRule(match={Strategy.NAME: "x"}, path="identity.emial"),))
    with pytest.raises(KeyError, match="identity.emial"):
        resolve((FormField(name="x", kind="text"),), field_map, package)
