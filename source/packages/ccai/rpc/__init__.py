"""
    codecraftai-python-rpc: an RPC layer for distributed automation with explicit passing semantics and
    callback threading that never blocks the thread waiting on a reply.
"""

from ccai.rpc.aspects import AspectsRpc, DEFAULT_RPC_ASPECTS, LoggingPattern, remaining_time, rpc_aspects_scope
from ccai.rpc.endpoints import ServiceEndpoint, IServiceEndpoint
from ccai.rpc.errors import (
    CancelledError, CompletionTimeout, ConnectionTimeout, InActivityTimeout, LeaseExpiredError, ProtocolError, RemoteError,
    RpcError, SerializationError, SessionClosedError, SessionError, TransportClosedError, UnauthorizedError, UnknownReferenceError,
)
from ccai.rpc.rpcsocketclient import RpcSocketClient
from ccai.rpc.rpcsocketserver import RpcSocketServer
from ccai.rpc.core.dispatch.context import check_cancelled, current_call_context, is_cancelled, report_progress
from ccai.rpc.core.flattenable import Flattenable
from ccai.rpc.core.futures import RemoteFuture, Progress, as_completed, wait_all
from ccai.rpc.core.leases import ILeaseAware
from ccai.rpc.core.proxy.remoteproxy import RemoteProxy
from ccai.rpc.core.proxy.wrappers import ByRef, ByValue, by_ref, concurrent_callbacks, expose_private, mutable_service, oneway
from ccai.rpc.core.serialization import register_dataclass, register_enum, register_flattenable
from ccai.rpc.core.session.base import rpc_context_scope

__all__ = [
    "AspectsRpc", "DEFAULT_RPC_ASPECTS", "LoggingPattern", "remaining_time", "rpc_aspects_scope", "rpc_context_scope",
    "ServiceEndpoint", "IServiceEndpoint", "RpcSocketClient", "RpcSocketServer",
    "CancelledError", "CompletionTimeout", "ConnectionTimeout", "InActivityTimeout", "LeaseExpiredError", "ProtocolError",
    "RemoteError", "RpcError", "SerializationError", "SessionClosedError", "SessionError", "TransportClosedError",
    "UnauthorizedError", "UnknownReferenceError",
    "check_cancelled", "current_call_context", "is_cancelled", "report_progress", "Flattenable",
    "RemoteFuture", "Progress", "as_completed", "wait_all", "RemoteProxy", "ILeaseAware",
    "ByRef", "ByValue", "by_ref", "concurrent_callbacks", "expose_private", "mutable_service", "oneway",
    "register_dataclass", "register_enum", "register_flattenable",
]
