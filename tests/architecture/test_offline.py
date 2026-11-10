"""RNF01: las pruebas corren sin red (pytest-socket con --disable-socket)."""

from __future__ import annotations

import socket

import pytest
from pytest_socket import SocketBlockedError


@pytest.mark.filterwarnings("ignore:A test tried to use socket:UserWarning")
def test_network_is_disabled_during_tests() -> None:
    with pytest.raises(SocketBlockedError):
        socket.socket(socket.AF_INET, socket.SOCK_STREAM)
