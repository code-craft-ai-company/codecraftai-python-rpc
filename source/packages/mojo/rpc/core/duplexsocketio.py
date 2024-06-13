"""
.. module:: duplexsocketstream
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Module that contains a DuplexSocketStream object which wraps a socket and provides message writing to and
               reading from the socket.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2024, Myron W Walker"
__credits__ = []


from typing import Tuple

import socket
import struct


from io import BytesIO


BUFFER_SIZE = 4096


class DuplexSocketIO:


    def __init__(self, sock: socket.socket, addr: Tuple[str, int]):

        self._sock = sock
        self._send_buffer = bytearray(BUFFER_SIZE)
        self._recv_buffer = bytearray(BUFFER_SIZE)

        return


    @property
    def sock(self) -> socket.socket:
        return self._sock


    def transmit_message(self, msg_bytes: bytes):

        msg_size = len(msg_bytes)
        remaining = msg_size

        buffer_view = memoryview(self._send_buffer)
        buffer_index = 0

        size_header = struct.pack("!Q", msg_size)
        self._sock.sendall(size_header)

        while remaining > 0:
            send_size = BUFFER_SIZE if remaining >= BUFFER_SIZE else remaining

            packet = buffer_view[buffer_index: send_size]
            bytes_sent = self._sock.send(packet)

            remaining = remaining - bytes_sent

        return


    def receive_message(self) -> bytes:

        # All message buffers must begin with an 8 byte size header
        size_header = self._sock.recv(8)

        msg_size = struct.unpack("!Q", size_header)
        
        buffer = BytesIO(msg_size)
        remaining = msg_size

        while remaining > 0:
            
            rcv_size = BUFFER_SIZE if remaining >= BUFFER_SIZE else remaining
            bytes_received = self._sock.recv_into(self._recv_buffer, rcv_size)

            if bytes_received < BUFFER_SIZE:
                buffer.write(self._recv_buffer[:bytes_received])
            else:
                buffer.write(self._recv_buffer)

            remaining = remaining - bytes_received

        msg_bytes = buffer.getvalue()

        return msg_bytes
