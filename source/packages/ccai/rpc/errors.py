"""
.. module:: errors
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Exception types used by the RPC package. Types that already exist in the suite's shared
               vocabulary are re-exported from ccai.errors so callers have one import point.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from ccai.errors.exceptions import (
    AbstractMethodError,
    CancelledError,
    CompletionTimeout,
    ConnectionTimeout,
    InActivityTimeout,
    LooperError,
    ProtocolError,
    SemanticError,
)


class RpcError(RuntimeError):
    """
        Base class for the errors this package adds to the shared vocabulary.
    """


class SerializationError(RpcError):
    """
        Raised when a value cannot be encoded for the wire or decoded from it.
    """


class TransportClosedError(RpcError):
    """
        Raised when a transport operation is attempted after the transport or its peer closed.
    """


class SessionError(RpcError):
    """
        Raised for misuse of a session, such as starting it twice.
    """


class SessionClosedError(SessionError):
    """
        Raised in callers whose outstanding requests were abandoned because the session closed.
    """


class UnknownReferenceError(RpcError):
    """
        Raised when a request names a reference id the owning side does not hold.
    """


class LeaseExpiredError(RpcError):
    """
        Raised when a request names a reference whose lease has lapsed.
    """


class UnauthorizedError(RpcError):
    """
        Raised when the server rejects a client's credential during the HELLO exchange.
    """


class RemoteError(RpcError):
    """
        Stands in for a remote exception whose type could not be resolved locally. Every decoded
        remote exception, including resolvable types, carries ``remote_traceback``.
    """

    def __init__(self, message: str, remote_type_name: str = "", remote_traceback: str = "") -> None:
        super().__init__(message)
        self.remote_type_name = remote_type_name
        self.remote_traceback = remote_traceback
        return

    def __str__(self) -> str:
        text = super().__str__()
        if self.remote_type_name:
            text = "{}: {}".format(self.remote_type_name, text)
        if self.remote_traceback:
            text = "{}\n\nRemote traceback:\n{}".format(text, self.remote_traceback)
        return text


__all__ = [
    "AbstractMethodError", "CancelledError", "CompletionTimeout", "ConnectionTimeout", "InActivityTimeout",
    "LooperError", "ProtocolError", "SemanticError", "RpcError", "SerializationError", "TransportClosedError",
    "SessionError", "SessionClosedError", "UnknownReferenceError", "LeaseExpiredError", "UnauthorizedError",
    "RemoteError",
]
