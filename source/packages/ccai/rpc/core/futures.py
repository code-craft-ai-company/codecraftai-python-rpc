"""
.. module:: futures
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RemoteFuture for asynchronous calls, with cancellation and progress delivery.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Callable, Dict, Generic, Iterable, Iterator, List, Optional, TypeVar

import threading
import time
import uuid

from ccai.rpc.errors import CancelledError, CompletionTimeout

T = TypeVar("T")


class Progress:

    __slots__ = ("fraction", "message", "details", "correlation_id", "received_at")

    def __init__(self, fraction: float, message: Optional[str], details: Dict, correlation_id: uuid.UUID) -> None:
        self.fraction = fraction
        self.message = message
        self.details = details
        self.correlation_id = correlation_id
        self.received_at = time.monotonic()
        return

    def __repr__(self) -> str:
        return "Progress({:.0%}{})".format(self.fraction, ", " + self.message if self.message else "")


class RemoteFuture(Generic[T]):
    """
        The result of an asynchronous remote call. Completed by the session when the reply or exception
        arrives, failed when the session closes, cancellable cooperatively.
    """

    def __init__(self, session, waiter, callable_name: str, deadline: Optional[float], unwrap: bool = False) -> None:
        self._session = session
        self._waiter = waiter
        self.correlation_id = waiter.correlation_id
        self.callable_name = callable_name
        self.started_at = time.monotonic()
        self.deadline = deadline
        self._unwrap = unwrap
        self._lock = threading.Lock()
        self._done_callbacks: List[Callable[["RemoteFuture"], None]] = []
        self._progress_callbacks: List[Callable[[Progress], None]] = []
        self.last_progress: Optional[Progress] = None
        self._cancelled = False
        self._result = None
        self._exception = None
        self._resolved = False
        waiter.on_complete = self._on_complete
        return

    # --------------------------------------------------------------- completion
    def _resolve(self) -> None:
        with self._lock:
            if self._resolved:
                return
            try:
                reply = self._session.resolve_reply(self._waiter)
                self._result = getattr(reply, "value", None) if self._unwrap else reply
            except BaseException as err:      # noqa: BLE001 - any failure is the future's exception
                self._exception = err
                if isinstance(err, CancelledError):
                    self._cancelled = True
            self._resolved = True
        return

    def _on_complete(self) -> None:
        self._resolve()
        for callback in list(self._done_callbacks):
            try:
                callback(self)
            except Exception:       # noqa: BLE001
                self._session.logger.exception("done callback for %s raised", self.callable_name)
        return

    def _deliver_progress(self, progress: Progress) -> None:
        self.last_progress = progress
        for callback in list(self._progress_callbacks):
            try:
                callback(progress)
            except Exception:       # noqa: BLE001
                self._session.logger.exception("progress callback for %s raised", self.callable_name)
        return

    # --------------------------------------------------------------- Future API
    def wait(self, timeout: Optional[float] = None) -> bool:
        return self._waiter.event.wait(timeout=timeout)

    def done(self) -> bool:
        return self._waiter.event.is_set()

    def cancelled(self) -> bool:
        return self._cancelled

    def result(self, timeout: Optional[float] = None) -> T:
        if not self.wait(timeout=timeout):
            raise CompletionTimeout("remote call '{}' did not complete within {}s".format(self.callable_name, timeout))
        self._resolve()
        if self._exception is not None:
            raise self._exception
        return self._result

    def exception(self, timeout: Optional[float] = None) -> Optional[BaseException]:
        if not self.wait(timeout=timeout):
            raise CompletionTimeout("remote call '{}' did not complete within {}s".format(self.callable_name, timeout))
        self._resolve()
        return self._exception

    def cancel(self) -> bool:
        if self.done():
            return False
        self._cancelled = True
        self._session.send_cancel(self.correlation_id)
        return True

    def add_done_callback(self, fn: Callable[["RemoteFuture"], None]) -> None:
        with self._lock:
            if not self.done():
                self._done_callbacks.append(fn)
                return
        fn(self)
        return

    def add_progress_callback(self, fn: Callable[[Progress], None]) -> None:
        self._progress_callbacks.append(fn)
        return

    def __repr__(self) -> str:
        state = "cancelled" if self._cancelled else "done" if self.done() else "pending"
        return "<RemoteFuture {} {}>".format(self.callable_name, state)


def wait_all(futures: Iterable[RemoteFuture], timeout: Optional[float] = None) -> bool:
    deadline = None if timeout is None else time.monotonic() + timeout
    for future in futures:
        remaining = None if deadline is None else max(0.0, deadline - time.monotonic())
        if not future.wait(timeout=remaining):
            return False
    return True


def as_completed(futures: Iterable[RemoteFuture], timeout: Optional[float] = None) -> Iterator[RemoteFuture]:
    pending = list(futures)
    deadline = None if timeout is None else time.monotonic() + timeout
    while pending:
        for future in list(pending):
            if future.done():
                pending.remove(future)
                yield future
        if not pending:
            break
        if deadline is not None and time.monotonic() > deadline:
            raise CompletionTimeout("{} remote call(s) still pending after {}s".format(len(pending), timeout))
        time.sleep(0.005)
    return
