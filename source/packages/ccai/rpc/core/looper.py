"""
.. module:: looper
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The Looper worker thread base class. Subclasses implement ``loop`` to process one packet.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Optional

import logging
import threading

from ccai.rpc.errors import AbstractMethodError, LooperError
from ccai.rpc.core.looperqueue import LooperQueue, LooperQueueShutdown

logger = logging.getLogger("ccai.rpc.dispatch")


class Looper:
    """
        A worker that owns one thread and repeatedly pops a packet from its queue and calls ``loop``.
        The thread exits when it pops a :class:`LooperQueueShutdown` sentinel or after ``stop`` was
        requested and the next packet arrives. The exit gate is set on every exit path.
    """

    def __init__(self, queue: LooperQueue, name: Optional[str] = None, group: Optional[str] = None,
                 daemon: Optional[bool] = None, **kwargs) -> None:
        self._queue = queue
        self._name = name
        self._group = group
        self._daemon = daemon
        self._kwargs = kwargs
        self._running = False
        self._stop_requested = False
        self._thread = None
        self._exit_gate = None
        return

    @property
    def name(self) -> str:
        if self._thread is not None:
            return self._thread.name
        return self._name if self._name is not None else "looper"

    @property
    def group(self) -> Optional[str]:
        return self._group

    @property
    def is_running(self) -> bool:
        return self._running

    def loop(self, packet: object) -> None:
        """
            Processes one packet. Overridden by derived classes.
        """
        raise AbstractMethodError("Looper: 'loop' must be overloaded by derived classes.")

    def start(self) -> None:
        """
            Starts the worker thread and returns once it has entered its work loop.
        """
        if self._thread is not None:
            raise LooperError("Looper: start called on a looper that was already started.")
        self._exit_gate = threading.Event()
        start_gate = threading.Event()
        self._thread = threading.Thread(target=self._loop_entry, name=self._name, args=(start_gate,), daemon=self._daemon)
        self._thread.start()
        start_gate.wait()
        return

    def stop(self) -> None:
        """
            Requests exit. The thread leaves its loop when the next packet arrives.
        """
        self._stop_requested = True
        return

    def wait_for_exit(self, timeout: Optional[float] = None) -> bool:
        """
            Waits for the thread to exit. Returns ``True`` when it has, ``False`` on timeout.
        """
        if self._exit_gate is None:
            raise LooperError("Looper: wait_for_exit called before the looper was started.")
        return self._exit_gate.wait(timeout=timeout)

    def _loop_entry(self, start_gate: threading.Event) -> None:
        self._running = True
        start_gate.set()
        try:
            while True:
                packet = self._queue.pop()
                if isinstance(packet, LooperQueueShutdown) or packet is None or self._stop_requested:
                    break
                try:
                    self.loop(packet)
                except Exception:
                    logger.exception("Looper %s: unhandled exception processing packet %r", self.name, packet)
        finally:
            self._running = False
            self._exit_gate.set()
        return
