"""
    Unit tests for :mod:`ccai.rpc.core.looper` and :mod:`ccai.rpc.core.looperpool` covering
    the abstract method guard, work processing and the misuse error paths.
"""

import threading
import unittest

from ccai.errors.exceptions import AbstractMethodError, LooperError

from ccai.rpc.core.looper import Looper
from ccai.rpc.core.looperpool import LooperPool
from ccai.rpc.core.looperqueue import LooperQueue, LooperQueueShutdown


class RecordingLooper(Looper):
    """
        A looper that records every packet it processes and signals when a packet arrives.
    """

    def __init__(self, queue: LooperQueue, name=None, group=None, daemon=None, **kwargs):
        super().__init__(queue, name=name, group=group, daemon=daemon, **kwargs)
        self.processed = []
        self.packet_seen = threading.Event()
        return

    def loop(self, packet) -> bool:
        self.processed.append(packet)
        self.packet_seen.set()
        return True


class TestLooperBase(unittest.TestCase):
    """
        Verify the base class guards.
    """

    def test_loop_must_be_overloaded(self) -> None:
        looper = Looper(LooperQueue())
        with self.assertRaises(AbstractMethodError):
            looper.loop("packet")
        return

    def test_wait_for_exit_before_start_raises(self) -> None:
        looper = Looper(LooperQueue())
        with self.assertRaises(LooperError):
            looper.wait_for_exit(timeout=0.01)
        return


class TestLooperProcessing(unittest.TestCase):
    """
        Verify a started looper processes queued work and exits on a shutdown sentinel.
    """

    def setUp(self) -> None:
        self.queue = LooperQueue()
        self.looper = RecordingLooper(self.queue, name="test-looper", daemon=True)
        self.looper.start()
        return

    def tearDown(self) -> None:
        # A sentinel pushed as work wakes the looper and makes its loop exit.
        self.queue.push_work(LooperQueueShutdown())
        self.looper._thread.join(timeout=2)
        self.assertFalse(self.looper._thread.is_alive())
        return

    def test_start_names_the_thread(self) -> None:
        self.assertEqual(self.looper.thread_get_name(), "test-looper")
        return

    def test_processes_pushed_packet(self) -> None:
        self.queue.push_work("hello")
        self.assertTrue(self.looper.packet_seen.wait(timeout=2))
        self.assertEqual(self.looper.processed, ["hello"])
        return


class TestLooperPoolGuards(unittest.TestCase):
    """
        Verify the pool rejects work before it is started.
    """

    def setUp(self) -> None:
        self.pool = LooperPool(RecordingLooper, group_name="test-pool", min_loopers=1, max_loopers=1, daemon=True)
        return

    def test_push_work_before_start_raises(self) -> None:
        with self.assertRaises(LooperError):
            self.pool.push_work("packet")
        return

    def test_push_work_packets_before_start_raises(self) -> None:
        with self.assertRaises(LooperError):
            self.pool.push_work_packets(["packet"])
        return


if __name__ == "__main__":
    unittest.main()
