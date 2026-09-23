"""
.. module:: socketio
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DuplexSocketIO, the Transport over a connected socket with complete-read guarantees.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Optional, Tuple

import socket
import struct
import threading

from ccai.rpc.errors import TransportClosedError
from ccai.rpc.core.protocol.constants import DEFAULT_MAX_MESSAGE_SIZE, FRAME_SIZE_BYTES
from ccai.rpc.core.protocol.header import read_frame_size
from ccai.rpc.core.transport.base import Transport, Upgrader

RECV_CHUNK = 64 * 1024


class DuplexSocketIO(Transport):

    def __init__(self, sock: socket.socket, receive_timeout: Optional[float] = None,
                 max_message_size: int = DEFAULT_MAX_MESSAGE_SIZE) -> None:
        self._sock = sock
        self._send_lock = threading.Lock()
        self._max_message_size = max_message_size
        self._open = True
        self._released = False
        self._pending = bytearray()      # bytes of the frame currently being read, kept across timeouts
        self._pending_size = None
        try:
            sock.setsockopt(socket.IPPROTO_TCP, socket.TCP_NODELAY, 1)
        except (OSError, AttributeError):
            # TCP_NODELAY is an optional latency optimization; sockets that are not TCP (for example a
            # socketpair) reject it and still work correctly without it.
            pass
        try:
            self._local = sock.getsockname()
            self._remote = sock.getpeername()
        except OSError:
            self._local = ("", 0)
            self._remote = ("", 0)
        sock.settimeout(receive_timeout)
        return

    @property
    def sock(self) -> socket.socket:
        return self._sock

    @property
    def local_address(self) -> Tuple[str, int]:
        return self._local if isinstance(self._local, tuple) and len(self._local) >= 2 else (str(self._local), 0)

    @property
    def remote_address(self) -> Tuple[str, int]:
        return self._remote if isinstance(self._remote, tuple) and len(self._remote) >= 2 else (str(self._remote), 0)

    @property
    def is_open(self) -> bool:
        return self._open

    def send_frame(self, message: bytes) -> None:
        if not self._open:
            raise TransportClosedError("send_frame on a closed transport")
        data = struct.pack("!Q", len(message)) + message
        with self._send_lock:
            try:
                self._sock.sendall(data)
            except OSError as err:
                self._open = False
                raise TransportClosedError("send failed: {}".format(err)) from err
        return

    def receive_frame(self) -> bytes:
        if not self._open:
            raise TransportClosedError("receive_frame on a closed transport")
        if self._pending_size is None:
            self._fill(FRAME_SIZE_BYTES)
            self._pending_size = read_frame_size(bytes(self._pending[:FRAME_SIZE_BYTES]), self._max_message_size)
            del self._pending[:FRAME_SIZE_BYTES]
        self._fill(self._pending_size)
        message = bytes(self._pending[:self._pending_size])
        del self._pending[:self._pending_size]
        self._pending_size = None
        return message

    def _fill(self, needed: int) -> None:
        """
            Reads until ``needed`` bytes are pending. A timeout keeps what was read so far.
        """
        while len(self._pending) < needed:
            want = min(needed - len(self._pending), RECV_CHUNK)
            try:
                chunk = self._sock.recv(want)
            except socket.timeout:
                raise TimeoutError("no data received within the receive timeout") from None
            except OSError as err:
                self._open = False
                raise TransportClosedError("receive failed: {}".format(err)) from err
            if len(chunk) == 0:
                self._open = False
                raise TransportClosedError("peer closed the connection: expected {} bytes, received {}".format(
                    needed, len(self._pending)))
            self._pending.extend(chunk)
        return

    def close(self) -> None:
        """
            Closes the socket. Safe to call more than once, and it always releases the descriptor even when
            an earlier send or receive failure already marked the transport closed.
        """
        self._open = False
        if self._released:
            return
        self._released = True
        try:
            self._sock.shutdown(socket.SHUT_RDWR)
        except OSError:
            # Best-effort; shutdown fails when the peer already disconnected, and the close below must
            # still run to release the descriptor.
            pass
        try:
            self._sock.close()
        except OSError:
            # Best-effort cleanup; a failure to close an already broken socket must not mask the error
            # that caused the transport to be closed.
            pass
        return

    def upgrade(self, upgrader: Upgrader) -> None:
        self._sock = upgrader(self._sock)
        return
