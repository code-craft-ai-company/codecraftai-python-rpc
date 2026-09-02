"""
.. module:: looperpool
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: A pool of Looper workers that grows with queue depth and shuts down in order.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import List, Optional, Sequence, Type

import threading

from ccai.rpc.errors import LooperError
from ccai.rpc.core.looper import Looper
from ccai.rpc.core.looperqueue import LooperQueue


class LooperPool:
    """
        Owns one :class:`LooperQueue` and a growable set of loopers. ``start_pool`` starts
        ``min_loopers``; each push that leaves more than ``highwater`` packets queued starts one more
        looper up to ``max_loopers``. The pool never shrinks; ``shutdown`` is how workers exit.
    """

    def __init__(self, looper_type: Type[Looper], group_name: str = "looper", min_loopers: int = 2,
                 max_loopers: int = 8, highwater: int = 4, daemon: bool = True, **looper_kwargs) -> None:
        if min_loopers < 1 or max_loopers < 1:
            raise LooperError("LooperPool: min_loopers and max_loopers must both be at least 1.")
        if min_loopers > max_loopers:
            raise LooperError("LooperPool: min_loopers={} is greater than max_loopers={}.".format(min_loopers, max_loopers))
        self._looper_type = looper_type
        self._group_name = group_name
        self._min_loopers = min_loopers
        self._max_loopers = max_loopers
        self._highwater = highwater
        self._daemon = daemon
        self._looper_kwargs = looper_kwargs
        self._queue = LooperQueue()
        self._lock = threading.RLock()
        self._loopers: List[Looper] = []
        self._running = False
        self._started = False
        return

    @property
    def is_running(self) -> bool:
        return self._running

    @property
    def worker_count(self) -> int:
        with self._lock:
            return len(self._loopers)

    @property
    def queue_depth(self) -> int:
        return self._queue.depth

    @property
    def group_name(self) -> str:
        return self._group_name

    def start_pool(self) -> None:
        with self._lock:
            if self._running:
                raise LooperError("LooperPool: start_pool called while the pool is already running.")
            if self._started:
                raise LooperError("LooperPool: a pool cannot be restarted after shutdown.")
            self._running = True
            self._started = True
            for _ in range(0, self._min_loopers):
                self._locked_start_looper()
        return

    def push_work(self, packet: object) -> int:
        self._check_running("push_work")
        depth = self._queue.push_work(packet)
        self._grow_if_needed(depth)
        return depth

    def push_work_packets(self, packets: Sequence[object]) -> int:
        self._check_running("push_work_packets")
        depth = self._queue.push_work_packets(packets)
        self._grow_if_needed(depth)
        return depth

    def shutdown(self, timeout: Optional[float] = None) -> List[Looper]:
        """
            Refuses further work, wakes every worker with a sentinel and waits for each to exit.
            Returns the workers that did not exit within the timeout.
        """
        with self._lock:
            self._running = False
            loopers = list(self._loopers)
            self._queue.shutdown(len(loopers))
        stragglers = []
        for looper in loopers:
            if not looper.wait_for_exit(timeout=timeout):
                stragglers.append(looper)
        return stragglers

    def describe(self) -> dict:
        with self._lock:
            return {
                "group": self._group_name,
                "running": self._running,
                "worker_count": len(self._loopers),
                "queue_depth": self._queue.depth,
                "min_loopers": self._min_loopers,
                "max_loopers": self._max_loopers,
                "highwater": self._highwater,
                "workers": [{"name": lp.name, "running": lp.is_running} for lp in self._loopers],
            }

    def _check_running(self, operation: str) -> None:
        if not self._running:
            raise LooperError("LooperPool: {} called while the pool is not running.".format(operation))
        return

    def _grow_if_needed(self, depth: int) -> None:
        if depth > self._highwater:
            with self._lock:
                if self._running and len(self._loopers) < self._max_loopers:
                    self._locked_start_looper()
        return

    def _locked_start_looper(self) -> None:
        index = len(self._loopers) + 1
        looper_name = "{}-{}".format(self._group_name, index)
        looper = self._looper_type(self._queue, name=looper_name, group=self._group_name, daemon=self._daemon, **self._looper_kwargs)
        looper.start()
        self._loopers.append(looper)
        return
