"""
.. module:: header
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The fixed 24 byte message header and the frame size helpers.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from dataclasses import dataclass

import struct
import uuid

from ccai.rpc.errors import ProtocolError
from ccai.rpc.core.protocol.constants import (
    DEFAULT_MAX_MESSAGE_SIZE, FRAME_SIZE_BYTES, HEADER_SIZE, MIN_SUPPORTED_VERSION, PROTOCOL_VERSION, MessageType,
)

_HEADER_FORMAT = "!HBB16sI"


@dataclass(frozen=True)
class MessageHeader:
    version: int
    mtype: MessageType
    mcode: int
    correlation_id: uuid.UUID
    payload_length: int

    def pack(self) -> bytes:
        return struct.pack(_HEADER_FORMAT, self.version, int(self.mtype), int(self.mcode), self.correlation_id.bytes, self.payload_length)

    @classmethod
    def unpack(cls, data: bytes) -> "MessageHeader":
        if len(data) < HEADER_SIZE:
            raise ProtocolError("message shorter than the {} byte header: {} bytes".format(HEADER_SIZE, len(data)))
        version, mtype_raw, mcode, cid_bytes, payload_length = struct.unpack(_HEADER_FORMAT, data[:HEADER_SIZE])
        if version < MIN_SUPPORTED_VERSION or version > PROTOCOL_VERSION:
            raise ProtocolError("unsupported protocol version {} (this end supports {} to {})".format(
                version, MIN_SUPPORTED_VERSION, PROTOCOL_VERSION))
        try:
            mtype = MessageType(mtype_raw)
        except ValueError:
            raise ProtocolError("unknown message type {}".format(mtype_raw)) from None
        return cls(version, mtype, mcode, uuid.UUID(bytes=cid_bytes), payload_length)


def frame(message: bytes) -> bytes:
    if len(message) == 0:
        raise ProtocolError("a zero-length message is invalid")
    return struct.pack("!Q", len(message)) + message


def read_frame_size(size_bytes: bytes, max_message_size: int = DEFAULT_MAX_MESSAGE_SIZE) -> int:
    if len(size_bytes) != FRAME_SIZE_BYTES:
        raise ProtocolError("frame size header must be {} bytes, got {}".format(FRAME_SIZE_BYTES, len(size_bytes)))
    size = struct.unpack("!Q", size_bytes)[0]
    if size == 0:
        raise ProtocolError("a zero-length message is invalid")
    if size > max_message_size:
        raise ProtocolError("frame announces {} bytes, above the maximum message size of {}".format(size, max_message_size))
    return size
