"""
.. module:: lanes
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Per-target ordering lanes: callbacks for one target run one at a time, in arrival order, without
               blocking pool workers.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Callable, Dict, Hashable, List

import threading


class TargetLane:

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._busy = False
        self._fifo: List[Callable[[], None]] = []
        return

    def run(self, work: Callable[[], None]) -> None:
        """
            Runs ``work`` now if the lane is free, otherwise queues it for the worker holding the lane, which
            drains the queue before releasing. Callers therefore never block on the lane.
        """
        with self._lock:
            if self._busy:
                self._fifo.append(work)
                return
            self._busy = True
        current = work
        while True:
            try:
                current()
            finally:
                with self._lock:
                    if self._fifo:
                        current = self._fifo.pop(0)
                        continue_ = True
                    else:
                        self._busy = False
                        continue_ = False
            if not continue_:
                break
        return

    @property
    def busy(self) -> bool:
        with self._lock:
            return self._busy


class LaneTable:

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._lanes: Dict[Hashable, TargetLane] = {}
        return

    def get(self, key: Hashable) -> TargetLane:
        with self._lock:
            lane = self._lanes.get(key)
            if lane is None:
                lane = TargetLane()
                self._lanes[key] = lane
            return lane

    def discard(self, key: Hashable) -> None:
        with self._lock:
            self._lanes.pop(key, None)
        return
