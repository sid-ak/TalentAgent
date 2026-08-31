"""The tool registry, where the autonomy boundary is structural rather than advisory.

The guardrails in Spec 10 are the product's central claim, and they are enforced in the policy
layer rather than in prompt text. A prompt-level guardrail is not a guardrail; it is a request.

Every tool declares a side-effect class from Spec Appendix C. Six of the seven classes are
agent-invocable. The seventh, `human-only`, is not: a tool in that class has no agent binding at
all. That is deliberately stronger than a permission check, because a permission check is something
a later refactor can route around without anyone noticing.
"""

from __future__ import annotations

import enum
from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import Any


class SideEffect(enum.Enum):
    """A tool's side-effect class (Spec Appendix C).

    The ordering here is from least to most consequential, and `HUMAN_ONLY` is last because it is
    the one class that never becomes agent-invocable.
    """

    PURE = "pure"
    READ = "read"
    WRITE_DRAFT = "write-draft"
    WRITE_USER_ORIGINATED = "write-user-originated"
    WRITE_REVERSIBLE = "write-reversible"
    WRITE_STAGED = "write-staged"
    HUMAN_ONLY = "human-only"

    @property
    def agent_invocable(self) -> bool:
        """Report whether an agent may be given this tool at all."""
        return self is not SideEffect.HUMAN_ONLY


class HumanOnlyToolError(RuntimeError):
    """Raised when a `human-only` tool is requested for an agent's tool set (G3)."""

    def __init__(self, name: str) -> None:
        """Record the tool that was refused."""
        self.name = name
        super().__init__(
            f"{name!r} is human-only and has no agent binding (G3). It is reachable only from a "
            f"human review action."
        )


@dataclass(frozen=True)
class Tool:
    """One entry in the registry.

    Attributes:
        name: The tool's name as agents refer to it.
        side_effect: Its side-effect class, which decides whether an agent may hold it.
        fn: The implementation.
        notes: The specification note for this tool, kept beside it rather than in a table.
    """

    name: str
    side_effect: SideEffect
    fn: Callable[..., Any]
    notes: str = ""


class Registry:
    """Holds every tool and decides which of them an agent may be handed."""

    def __init__(self) -> None:
        """Start an empty registry."""
        self._tools: dict[str, Tool] = {}

    def register(
        self,
        name: str,
        side_effect: SideEffect,
        fn: Callable[..., Any],
        notes: str = "",
    ) -> Tool:
        """Add a tool to the registry.

        Raises:
            TypeError: if `side_effect` is not a SideEffect, so a tool cannot be registered
                without declaring its class.
            ValueError: if the name is already registered.
        """
        if not isinstance(side_effect, SideEffect):
            raise TypeError(
                f"Tool {name!r} must declare a side-effect class from Spec Appendix C; "
                f"got {side_effect!r}."
            )
        if name in self._tools:
            raise ValueError(f"Tool {name!r} is already registered.")
        tool = Tool(name=name, side_effect=side_effect, fn=fn, notes=notes)
        self._tools[name] = tool
        return tool

    def get(self, name: str) -> Tool:
        """Return the registered tool called `name`."""
        return self._tools[name]

    def __iter__(self) -> Iterator[Tool]:
        """Iterate over every registered tool, whatever its class."""
        return iter(self._tools.values())

    def __len__(self) -> int:
        """Return the number of registered tools."""
        return len(self._tools)

    def agent_toolset(self, *names: str) -> dict[str, Tool]:
        """Build an agent's tool set, refusing any `human-only` tool.

        This is the single place an agent acquires tools, so G3 holds by construction rather than
        by every agent definition remembering to check.

        Raises:
            HumanOnlyToolError: if any requested tool is human-only.
            KeyError: if a requested tool is not registered.
        """
        toolset: dict[str, Tool] = {}
        for name in names:
            tool = self._tools[name]
            if not tool.side_effect.agent_invocable:
                raise HumanOnlyToolError(name)
            toolset[name] = tool
        return toolset

    def human_only(self) -> tuple[Tool, ...]:
        """Return every tool an agent can never hold."""
        return tuple(t for t in self if not t.side_effect.agent_invocable)
