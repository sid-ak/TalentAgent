"""Session-wide test configuration.

The zero-network fixture here is the primary control on the Gemini free-tier quota (ADR-0012):
recorded golden responses are only a saving if nothing in the suite can reach a live model. It is
also what makes the suite deterministic, which is the harder problem to notice going wrong.
"""

import socket
from collections.abc import Iterator

import pytest


class NetworkAccessDenied(RuntimeError):
    """Raised when a test attempts an outbound connection."""


def _deny(*_args: object, **_kwargs: object) -> None:
    """Stand in for socket.socket, refusing every outbound connection attempt."""
    raise NetworkAccessDenied(
        "This test attempted an outbound network connection. The suite makes zero API calls "
        "(ADR-0012): record a golden response with `python -m talentagent.models.record` and "
        "replay it, or mark the test `@pytest.mark.network` if it needs the emulator."
    )


@pytest.fixture(autouse=True)
def _no_network(request: pytest.FixtureRequest) -> Iterator[None]:
    """Refuse outbound connections unless the test is explicitly marked `network`."""
    if request.node.get_closest_marker("network"):
        yield
        return
    original = socket.socket
    socket.socket = _deny  # type: ignore[assignment,misc]
    try:
        yield
    finally:
        socket.socket = original  # type: ignore[misc]
