"""
.. module:: base
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The Transport interface sessions program against, and the forwarding TransportWrapper.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Callable, Tuple

import socket

from ccai.rpc.errors import AbstractMethodError

Upgrader = Callable[[socket.socket], socket.socket]


class Transport:
    """
        Moves whole frames between two endpoints. ``receive_frame`` blocks until a full frame is available
        or the transport is closed; concurrent ``send_frame`` calls are serialised by the implementation.
    """

    @property
    def local_address(self) -> Tuple[str, int]:
        raise AbstractMethodError("Transport.local_address must be implemented")

    @property
    def remote_address(self) -> Tuple[str, int]:
        raise AbstractMethodError("Transport.remote_address must be implemented")

    @property
    def is_open(self) -> bool:
        raise AbstractMethodError("Transport.is_open must be implemented")

    def send_frame(self, message: bytes) -> None:
        raise AbstractMethodError("Transport.send_frame must be implemented")

    def receive_frame(self) -> bytes:
        raise AbstractMethodError("Transport.receive_frame must be implemented")

    def close(self) -> None:
        raise AbstractMethodError("Transport.close must be implemented")

    def upgrade(self, upgrader: Upgrader) -> None:
        raise AbstractMethodError("Transport.upgrade must be implemented")


class TransportWrapper(Transport):
    """
        Forwards every operation to an inner transport. Subclasses override what they change.
    """

    def __init__(self, inner: Transport) -> None:
        self._inner = inner
        return

    @property
    def inner(self) -> Transport:
        return self._inner

    @property
    def local_address(self) -> Tuple[str, int]:
        return self._inner.local_address

    @property
    def remote_address(self) -> Tuple[str, int]:
        return self._inner.remote_address

    @property
    def is_open(self) -> bool:
        return self._inner.is_open

    def send_frame(self, message: bytes) -> None:
        self._inner.send_frame(message)
        return

    def receive_frame(self) -> bytes:
        return self._inner.receive_frame()

    def close(self) -> None:
        self._inner.close()
        return

    def upgrade(self, upgrader: Upgrader) -> None:
        self._inner.upgrade(upgrader)
        return
