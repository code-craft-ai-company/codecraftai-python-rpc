"""
.. module:: constants
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Protocol versions, sizes and the message type and code vocabularies.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from enum import IntEnum

PROTOCOL_VERSION = 1
MIN_SUPPORTED_VERSION = 1
HEADER_SIZE = 24
FRAME_SIZE_BYTES = 8
DEFAULT_MAX_MESSAGE_SIZE = 64 * 1024 * 1024


class MessageType(IntEnum):
    REQUEST = 1
    REPLY = 2
    EXCEPTION = 3


class RequestCode(IntEnum):
    HELLO = 1
    PING = 2
    CLOSE = 3
    GETSERVICE = 4
    GETATTR = 5
    SETATTR = 6
    DELATTR = 7
    CALL = 8
    RELEASE = 9
    RENEW = 10
    CANCEL = 11
    PROGRESS = 12


class ReplyCode(IntEnum):
    HELLO = 1
    PING = 2
    CLOSE = 3
    GETSERVICE = 4
    GETATTR = 5
    SETATTR = 6
    DELATTR = 7
    CALL = 8
    RELEASE = 9
    RENEW = 10
    CANCEL = 11
    PROGRESS = 12


class ExceptionCode(IntEnum):
    REMOTE_EXCEPTION = 1
    PROTOCOL_ERROR = 2
    UNKNOWN_REFERENCE = 3
    LEASE_EXPIRED = 4
    CANCELLED = 5
    UNAUTHORIZED = 6
