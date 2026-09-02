"""
.. module:: aspects
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: AspectsRpc, the behaviour-parameter bundle for every tunable in the package, plus the per-thread
               override scope and the deadline helper for service code.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Iterator, Optional

import contextlib
import threading

from enum import IntEnum

from ccai.aspects.aspects import Aspects
from ccai.errors.exceptions import SemanticError

from ccai.rpc.core.serialization.registry import register_flattenable


class LoggingPattern(IntEnum):
    ALL_RESULTS = 0
    FAILURE_ONLY = 1
    SUCCESS_ONLY = 2


class AspectsRpc(Aspects):
    """
        Every tunable of the RPC layer in one frozen object. Connect behaviour comes from the base fields
        (``connection_timeout`` per attempt, ``max_attempts``, ``completion_interval`` between attempts);
        ``completion_timeout`` is the default per-call response timeout and the deadline sent with each
        request. The RPC-specific fields are named for what they tune so a reader of
        ``AspectsRpc(inactivity_timeout=5)`` knows dead-peer detection is being changed, not a call timeout.
    """

    def __init__(self, *,
                 completion_interval: float = 2.0,
                 completion_timeout: float = 600.0,
                 connection_timeout: float = 30.0,
                 max_attempts: int = 1,
                 logger_name: Optional[str] = None,
                 heartbeat_interval: float = 10.0,
                 inactivity_timeout: float = 60.0,
                 lease_duration: float = 90.0,
                 dispatch_min_workers: int = 2,
                 dispatch_max_workers: int = 8,
                 dispatch_highwater: int = 4,
                 logging_pattern: LoggingPattern = LoggingPattern.FAILURE_ONLY,
                 retry_logging_interval: float = 5.0) -> None:
        super().__init__(completion_interval=completion_interval, completion_timeout=completion_timeout,
                         connection_timeout=connection_timeout, max_attempts=max_attempts, logger_name=logger_name)
        self.heartbeat_interval = heartbeat_interval
        self.inactivity_timeout = inactivity_timeout
        self.lease_duration = lease_duration
        self.dispatch_min_workers = dispatch_min_workers
        self.dispatch_max_workers = dispatch_max_workers
        self.dispatch_highwater = dispatch_highwater
        self.logging_pattern = LoggingPattern(logging_pattern)
        self.retry_logging_interval = retry_logging_interval
        self._validate()
        self.freeze()
        return

    def _validate(self) -> None:
        for name in ("completion_interval", "completion_timeout", "connection_timeout", "heartbeat_interval",
                     "inactivity_timeout", "lease_duration", "retry_logging_interval"):
            value = getattr(self, name)
            if not isinstance(value, (int, float)) or value <= 0:
                raise SemanticError("AspectsRpc: '{}' must be a positive number, got {!r}".format(name, value))
        if self.max_attempts < 1:
            raise SemanticError("AspectsRpc: 'max_attempts' must be at least 1")
        if self.dispatch_min_workers < 1 or self.dispatch_max_workers < 1:
            raise SemanticError("AspectsRpc: dispatch worker counts must be at least 1")
        if self.dispatch_min_workers > self.dispatch_max_workers:
            raise SemanticError("AspectsRpc: 'dispatch_min_workers' may not exceed 'dispatch_max_workers'")
        if self.lease_duration < 2 * self.heartbeat_interval:
            raise SemanticError("AspectsRpc: 'lease_duration' ({}) must be at least twice 'heartbeat_interval' ({})".format(
                self.lease_duration, self.heartbeat_interval))
        return

    FIELDS = ("completion_interval", "completion_timeout", "connection_timeout", "max_attempts", "logger_name",
              "heartbeat_interval", "inactivity_timeout", "lease_duration", "dispatch_min_workers",
              "dispatch_max_workers", "dispatch_highwater", "logging_pattern", "retry_logging_interval")

    def replace(self, **changes) -> "AspectsRpc":
        values = {name: getattr(self, name) for name in self.FIELDS}
        for name in changes:
            if name not in values:
                raise SemanticError("AspectsRpc.replace: unknown field '{}'".format(name))
        values.update(changes)
        return AspectsRpc(**values)

    def flatten(self) -> dict:
        data = {name: getattr(self, name) for name in self.FIELDS}
        data["logging_pattern"] = int(self.logging_pattern)
        return data

    @classmethod
    def unflatten(cls, data: dict) -> "AspectsRpc":
        return cls(**data)

    def __repr__(self) -> str:
        return "AspectsRpc({})".format(", ".join("{}={!r}".format(n, getattr(self, n)) for n in self.FIELDS))


register_flattenable("ccai.rpc.aspects", AspectsRpc)

DEFAULT_RPC_ASPECTS = AspectsRpc()

_scope = threading.local()


def current_aspects_override() -> Optional[AspectsRpc]:
    return getattr(_scope, "aspects", None)


@contextlib.contextmanager
def rpc_aspects_scope(aspects: AspectsRpc) -> Iterator[None]:
    """
        Applies ``aspects`` to every request made on this thread within the block.
    """
    previous = getattr(_scope, "aspects", None)
    _scope.aspects = aspects
    try:
        yield
    finally:
        _scope.aspects = previous
    return


def remaining_time() -> Optional[float]:
    """
        Seconds until the current call's deadline, or ``None`` outside a call or without a deadline.
    """
    from ccai.rpc.core.dispatch.context import remaining_time as _remaining
    return _remaining()


__all__ = ["AspectsRpc", "DEFAULT_RPC_ASPECTS", "LoggingPattern", "rpc_aspects_scope", "remaining_time", "current_aspects_override"]
