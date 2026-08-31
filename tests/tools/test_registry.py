"""Pins registration semantics and the escalation outcome (issue #6)."""

import pytest
from talentagent.tools.catalog import build_registry
from talentagent.tools.escalation import Escalation, EscalationLog
from talentagent.tools.registry import Registry, SideEffect


def test_registering_without_a_side_effect_class_fails() -> None:
    """A tool cannot be registered without a class, so none can be assigned conveniently later."""
    registry = Registry()
    with pytest.raises(TypeError, match="side-effect class"):
        registry.register("thing", "read", lambda: None)  # type: ignore[arg-type]


def test_duplicate_registration_is_refused() -> None:
    """Two tools cannot share a name, so a lookup is unambiguous."""
    registry = Registry()
    registry.register("thing", SideEffect.PURE, lambda: None)
    with pytest.raises(ValueError, match="already registered"):
        registry.register("thing", SideEffect.READ, lambda: None)


def test_catalog_declares_every_tool_in_the_specification() -> None:
    """All twelve tools in Spec 9.1 are present with the classes the table gives them."""
    registry = build_registry()
    assert len(registry) == 12
    assert registry.get("fill_application").side_effect is SideEffect.WRITE_STAGED
    assert registry.get("draft_followup").side_effect is SideEffect.WRITE_DRAFT
    assert registry.get("hold_calendar_slot").side_effect is SideEffect.WRITE_REVERSIBLE
    assert registry.get("promote_statement").side_effect is SideEffect.WRITE_USER_ORIGINATED


def test_escalation_rate_is_reported_per_decision_point() -> None:
    """The rate is grouped by decision point, so a spike localises the weak contract."""
    log = EscalationLog()
    log.record_decision("pipeline.transition")
    log.record_escalation(Escalation("pipeline.transition", "ambiguous thread"))
    log.record_decision("composer.compose")
    assert log.rate("pipeline.transition") == pytest.approx(0.5)
    assert log.rate("composer.compose") == pytest.approx(0.0)
    assert set(log.rates()) == {"pipeline.transition", "composer.compose"}
