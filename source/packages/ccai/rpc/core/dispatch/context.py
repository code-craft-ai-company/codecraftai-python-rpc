"""
.. module:: context
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The per-thread call context a dispatch worker exposes while executing a request, and the helpers
               service code uses to read the deadline, observe cancellation and report progress.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Dict, Optional

import threading
import time
import uuid

from ccai.errors.exceptions import SemanticError

from ccai.rpc.errors import CancelledError


class CallContext:
    """
        What a dispatch worker knows about the request it is executing.
    """

    __slots__ = ("session", "correlation_id", "caller_session_id", "target_ref", "callable_name", "started_at",
                 "deadline", "caller_context", "_cancelled", "notify")

    def __init__(self, session, correlation_id: uuid.UUID, caller_session_id: Optional[uuid.UUID],
                 target_ref: Optional[uuid.UUID], callable_name: str, deadline: Optional[float],
                 caller_context: Optional[Dict[str, str]] = None, notify: bool = False) -> None:
        self.session = session
        self.correlation_id = correlation_id
        self.caller_session_id = caller_session_id
        self.target_ref = target_ref
        self.callable_name = callable_name
        self.started_at = time.monotonic()
        self.deadline = deadline                    # monotonic time or None
        self.caller_context = dict(caller_context or {})
        self.notify = notify
        self._cancelled = threading.Event()
        return

    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.started_at

    @property
    def remaining(self) -> Optional[float]:
        if self.deadline is None:
            return None
        return self.deadline - time.monotonic()

    def cancel(self) -> None:
        self._cancelled.set()
        return

    @property
    def is_cancelled(self) -> bool:
        if self._cancelled.is_set():
            return True
        remaining = self.remaining
        return remaining is not None and remaining <= 0

    def describe(self) -> dict:
        return {"correlation_id": str(self.correlation_id), "callable": self.callable_name,
                "target_ref": str(self.target_ref) if self.target_ref else None, "elapsed": round(self.elapsed, 3),
                "remaining": None if self.remaining is None else round(self.remaining, 3), "cancelled": self.is_cancelled}


_current = threading.local()


def set_call_context(context: Optional[CallContext]) -> None:
    _current.context = context
    return


def current_call_context() -> Optional[CallContext]:
    return getattr(_current, "context", None)


def remaining_time() -> Optional[float]:
    context = current_call_context()
    if context is None:
        return None
    return context.remaining


def is_cancelled() -> bool:
    context = current_call_context()
    return context is not None and context.is_cancelled


def check_cancelled() -> None:
    context = current_call_context()
    if context is not None and context.is_cancelled:
        raise CancelledError("call '{}' ({}) was cancelled by the caller or its deadline passed".format(
            context.callable_name, context.correlation_id))
    return


def report_progress(fraction: float, message: Optional[str] = None, **details) -> None:
    """
        Sends a progress notification for the current call. Raises outside a call context.
    """
    context = current_call_context()
    if context is None:
        raise SemanticError("report_progress called outside of an RPC call context")
    context.session.send_progress(context.correlation_id, float(fraction), message, dict(details))
    return
