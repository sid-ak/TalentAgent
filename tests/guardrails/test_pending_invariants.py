"""G1, G2, G4, and G6: invariants whose enforcement arrives in a later phase.

Held here as xfail so the suite is a complete map of Spec 10 from the start. An invariant that is
only added to the suite when its code lands is an invariant nobody notices is missing.
"""

import pytest

pytestmark = pytest.mark.guardrail


@pytest.mark.xfail(reason="G1: derived quarantine arrives with issue #21", strict=True)
def test_g1_no_model_originated_claim_reaches_an_employer() -> None:
    """No accomplishment of class `derived` can be selected by the composer."""
    raise AssertionError("not yet enforced")


@pytest.mark.xfail(reason="G2: package schema validation arrives with issue #25", strict=True)
def test_g2_no_generated_line_without_a_credit() -> None:
    """Every generated line carries at least one credit resolving to an admissible node."""
    raise AssertionError("not yet enforced")


@pytest.mark.xfail(reason="G4: ranking-layer check arrives with issue #43", strict=True)
def test_g4_no_suppression_by_self_derived_signal() -> None:
    """`may_exclude` is false on every prior record, and no prior can remove an opportunity."""
    raise AssertionError("not yet enforced")


def test_g6_no_credential_handling_path_exists() -> None:
    """No tool in the registry creates an account or handles a password (G6).

    The three target platforms accept applications without a candidate account (Spec 8.3), so this
    holds by there being nothing to enforce against — which is the strongest form it can take.
    """
    from talentagent.tools.catalog import build_registry

    forbidden = ("password", "credential", "login", "authenticate", "create_account", "signin")
    for tool in build_registry():
        assert not any(word in tool.name.lower() for word in forbidden)
