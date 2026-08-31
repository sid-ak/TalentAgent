"""G3: no irreversible autonomy. Submit, send, accept, and decline are human-only classes."""

import pytest
from talentagent.tools.catalog import AGENT_TOOLSETS, build_registry
from talentagent.tools.registry import HumanOnlyToolError, Registry, SideEffect

pytestmark = pytest.mark.guardrail


@pytest.fixture
def registry() -> Registry:
    """The full tool registry as Spec 9.1 declares it."""
    return build_registry()


def test_submit_application_is_human_only(registry: Registry) -> None:
    """The submit tool carries the one class that is never agent-invocable."""
    assert registry.get("submit_application").side_effect is SideEffect.HUMAN_ONLY
    assert not registry.get("submit_application").side_effect.agent_invocable


def test_no_agent_toolset_reaches_a_human_only_tool(registry: Registry) -> None:
    """Walking every agent entry point, no path reaches a human-only tool.

    This is the reachability assertion: it enumerates the agents rather than testing one call, so
    binding a human-only tool into any agent fails here rather than in review.
    """
    human_only = {tool.name for tool in registry.human_only()}
    assert human_only, "the registry must declare at least one human-only tool"
    for agent, names in AGENT_TOOLSETS.items():
        toolset = registry.agent_toolset(*names)
        assert not human_only & set(toolset), f"{agent} reaches a human-only tool"


def test_binding_a_human_only_tool_into_an_agent_is_refused(registry: Registry) -> None:
    """Requesting submit_application for an agent raises rather than silently omitting it."""
    with pytest.raises(HumanOnlyToolError, match="human-only"):
        registry.agent_toolset("fetch_posting", "submit_application")


def test_every_agent_in_the_roster_has_a_declared_toolset() -> None:
    """All five agents in Spec 2.1 are covered, so none is exempt from the reachability walk."""
    assert set(AGENT_TOOLSETS) == {"triage", "pipeline", "evidence", "composer", "analyst"}
