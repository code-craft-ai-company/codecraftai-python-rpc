"""
.. module:: looperqueue
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: A thread-safe work queue coupling a list, a counting semaphore and a lock, shared by the
               LooperPool producer and its Looper workers.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Optional, Sequence

import threading

from ccai.rpc.errors import LooperError


class LooperQueueShutdown:
    """
        Sentinel packet. A worker that pops one exits its loop.
    """

    def __repr__(self) -> str:
        return "LooperQueueShutdown()"


class LooperQueue:
    """
        Thread-safe queue. The semaphore count always equals the number of packets appended and not
        yet popped, which is what makes one wake-up per packet, and therefore shutdown, reliable.
    """

    def __init__(self) -> None:
        self._queue = []
        self._available = threading.Semaphore(value=0)
        self._lock = threading.RLock()
        self._shutdown = False
        return

    @property
    def depth(self) -> int:
        with self._lock:
            return len(self._queue)

    @property
    def is_shutdown(self) -> bool:
        with self._lock:
            return self._shutdown

    def push_work(self, packet: object) -> int:
        """
            Appends one packet and signals one available packet. Returns the resulting depth.
        """
        with self._lock:
            if self._shutdown:
                raise LooperError("LooperQueue: the queue is shut down, no more work is allowed to be queued.")
            self._queue.append(packet)
            depth = len(self._queue)
        self._available.release()
        return depth

    def push_work_packets(self, packets: Sequence[object]) -> int:
        """
            Appends every packet and signals once per packet. Returns the resulting depth.
        """
        packets = list(packets)
        with self._lock:
            if self._shutdown:
                raise LooperError("LooperQueue: the queue is shut down, no more work is allowed to be queued.")
            self._queue.extend(packets)
            depth = len(self._queue)
        for _ in packets:
            self._available.release()
        return depth

    def pop(self, timeout: Optional[float] = None) -> Optional[object]:
        """
            Blocks until a packet is available and returns it in first-in, first-out order. With a
            timeout, returns ``None`` when nothing became available in time.
        """
        acquired = self._available.acquire(timeout=timeout) if timeout is not None else self._available.acquire()
        if not acquired:
            return None
        with self._lock:
            if len(self._queue) == 0:
                return None
            return self._queue.pop(0)

    def shutdown(self, worker_count: int) -> None:
        """
            Marks the queue shut down and appends one sentinel per worker, signalling each, so every
            blocked worker wakes exactly once after the pending work drains.
        """
        with self._lock:
            self._shutdown = True
            for _ in range(0, worker_count):
                self._queue.append(LooperQueueShutdown())
        for _ in range(0, worker_count):
            self._available.release()
        return
