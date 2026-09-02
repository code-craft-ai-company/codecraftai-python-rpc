"""
.. module:: faults
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: A transport wrapper that drops, delays, truncates or closes on command, for failure-path tests.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import List

import threading
import time

from ccai.rpc.core.transport.base import Transport, TransportWrapper


class FaultInjectingTransport(TransportWrapper):

    def __init__(self, inner: Transport) -> None:
        super().__init__(inner)
        self._lock = threading.Lock()
        self._drop = 0
        self._delay = 0.0
        self._truncate = 0
        self._close_after = None
        self._sent = 0
        self._actions: List[str] = []
        return

    @property
    def actions(self) -> List[str]:
        with self._lock:
            return list(self._actions)

    def drop_next(self, count: int) -> None:
        with self._lock:
            self._drop = count
        return

    def delay_frames(self, seconds: float) -> None:
        with self._lock:
            self._delay = seconds
        return

    def truncate_next(self, count: int = 1) -> None:
        with self._lock:
            self._truncate = count
        return

    def close_after(self, count: int) -> None:
        with self._lock:
            self._close_after = count
        return

    def send_frame(self, message: bytes) -> None:
        with self._lock:
            if self._drop > 0:
                self._drop -= 1
                self._actions.append("dropped")
                return
            delay = self._delay
            truncate = self._truncate > 0
            if truncate:
                self._truncate -= 1
            self._sent += 1
            close_now = self._close_after is not None and self._sent >= self._close_after
        if delay:
            self._actions.append("delayed {}s".format(delay))
            time.sleep(delay)
        if truncate:
            self._actions.append("truncated")
            message = message[: max(1, len(message) // 2)]
        self._inner.send_frame(message)
        if close_now:
            self._actions.append("closed")
            self._inner.close()
        return
