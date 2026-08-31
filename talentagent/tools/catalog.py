"""The registry as the specification declares it (Spec 9.1).

Implementations arrive phase by phase. What is fixed from the start is the name and the side-effect
class of every tool, because that is what the guardrail suite asserts against — and a class that is
assigned late is a class that can be assigned conveniently.
"""

from __future__ import annotations

from typing import Any, NoReturn

from talentagent.tools.registry import Registry, SideEffect


def _not_yet_implemented(name: str, issue: str) -> Any:
    """Build a placeholder that names the issue which will implement it."""

    def placeholder(*_args: object, **_kwargs: object) -> NoReturn:
        raise NotImplementedError(f"{name} arrives with {issue}.")

    placeholder.__name__ = name
    placeholder.__doc__ = f"Placeholder for {name}; implemented by {issue}."
    return placeholder


def build_registry() -> Registry:
    """Build the full tool registry from Spec 9.1."""
    registry = Registry()
    declared: tuple[tuple[str, SideEffect, str, str], ...] = (
        ("classify_message", SideEffect.PURE, "#32", "Tier-1 backed"),
        ("fetch_posting", SideEffect.READ, "#13", "Permitted-domain list enforced at fetch layer"),
        ("query_evidence", SideEffect.READ, "#23", "Returns candidates, sufficiency, class"),
        ("score_eligibility", SideEffect.READ, "#41", "Structured filings only; may gate"),
        ("score_prior", SideEffect.READ, "#42", "Returns interval and state; rank-only"),
        ("run_segment_analysis", SideEffect.READ, "#44", "In-process over the outcome log"),
        ("elicit_evidence", SideEffect.WRITE_DRAFT, "#26", "One scoped question; cannot author"),
        (
            "promote_statement",
            SideEffect.WRITE_USER_ORIGINATED,
            "#26",
            "The user's raw text becomes a Statement",
        ),
        ("draft_followup", SideEffect.WRITE_DRAFT, "#37", "Produces a draft; cannot send"),
        ("hold_calendar_slot", SideEffect.WRITE_REVERSIBLE, "#37", "Tentative holds only"),
        ("fill_application", SideEffect.WRITE_STAGED, "#14", "Fills and captures; cannot submit"),
        (
            "submit_application",
            SideEffect.HUMAN_ONLY,
            "#50",
            "Not exposed to any agent; reachable only from a human review action",
        ),
    )
    for name, side_effect, issue, notes in declared:
        registry.register(name, side_effect, _not_yet_implemented(name, issue), notes)
    return registry


AGENT_TOOLSETS: dict[str, tuple[str, ...]] = {
    "triage": ("classify_message",),
    "pipeline": ("draft_followup", "hold_calendar_slot"),
    "evidence": ("elicit_evidence", "promote_statement"),
    "composer": ("fetch_posting", "query_evidence", "score_eligibility", "fill_application"),
    "analyst": ("score_prior", "run_segment_analysis"),
}
"""Agents and the tools each is permitted to hold.

The guardrail suite walks this to prove that no agent entry point reaches a human-only
tool (G3).
"""
