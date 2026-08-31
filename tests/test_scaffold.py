"""Pins that the project scaffold itself works, so a green suite means the harness ran."""

import pytest

from tests.conftest import NetworkAccessDenied


def test_package_imports() -> None:
    """The package imports and reports a version."""
    import talentagent

    assert talentagent.__version__


def test_outbound_network_is_refused() -> None:
    """An outbound connection raises, with a message naming the golden-fixture mechanism."""
    import socket

    with pytest.raises(NetworkAccessDenied, match="zero API calls"):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
