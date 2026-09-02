"""
    Unit tests for :mod:`ccai.rpc.core.looperpool`.
"""

import threading
import time
import unittest

from ccai.rpc.errors import LooperError
from ccai.rpc.core.looper import Looper
from ccai.rpc.core.looperpool import LooperPool


class BlockingLooper(Looper):
    """
        Blocks on each packet until the test releases it, so queue depth can be controlled.
    """

    gate = threading.Event()
    processed = []
    lock = threading.Lock()

    def loop(self, packet) -> None:
        BlockingLooper.gate.wait(timeout=5)
        with BlockingLooper.lock:
            BlockingLooper.processed.append(packet)
        return


class TestLooperPoolValidation(unittest.TestCase):

    def test_bad_sizes_raise(self) -> None:
        with self.assertRaises(LooperError):
            LooperPool(BlockingLooper, min_loopers=0)
        with self.assertRaises(LooperError):
            LooperPool(BlockingLooper, min_loopers=3, max_loopers=2)
        return

    def test_push_before_start_raises(self) -> None:
        pool = LooperPool(BlockingLooper, group_name="p", min_loopers=1, max_loopers=1)
        with self.assertRaises(LooperError):
            pool.push_work("x")
        with self.assertRaises(LooperError):
            pool.push_work_packets(["x"])
        return


class TestLooperPoolLifecycle(unittest.TestCase):

    def setUp(self) -> None:
        BlockingLooper.gate = threading.Event()
        BlockingLooper.processed = []
        self.pool = LooperPool(BlockingLooper, group_name="pool", min_loopers=2, max_loopers=4, highwater=2, daemon=True)
        self.pool.start_pool()
        return

    def tearDown(self) -> None:
        BlockingLooper.gate.set()
        stragglers = self.pool.shutdown(timeout=5)
        self.assertEqual(stragglers, [])
        return

    def test_starts_minimum_workers_with_names(self) -> None:
        self.assertEqual(self.pool.worker_count, 2)
        self.assertEqual([w["name"] for w in self.pool.describe()["workers"]], ["pool-1", "pool-2"])
        self.assertTrue(self.pool.is_running)
        return

    def test_restart_raises(self) -> None:
        with self.assertRaises(LooperError):
            self.pool.start_pool()
        return

    def test_grows_past_highwater_up_to_max(self) -> None:
        for i in range(10):
            self.pool.push_work(i)
        self.assertEqual(self.pool.worker_count, 4)
        BlockingLooper.gate.set()
        deadline = time.monotonic() + 5
        while len(BlockingLooper.processed) < 10 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(sorted(BlockingLooper.processed), list(range(10)))
        return

    def test_describe_shape(self) -> None:
        described = self.pool.describe()
        self.assertEqual(described["group"], "pool")
        self.assertEqual(described["max_loopers"], 4)
        self.assertIn("queue_depth", described)
        return


class TestLooperPoolShutdown(unittest.TestCase):

    def test_shutdown_stops_workers_and_refuses_work(self) -> None:
        BlockingLooper.gate = threading.Event()
        BlockingLooper.gate.set()
        pool = LooperPool(BlockingLooper, group_name="s", min_loopers=3, max_loopers=3, daemon=True)
        pool.start_pool()
        self.assertEqual(pool.shutdown(timeout=5), [])
        self.assertFalse(pool.is_running)
        with self.assertRaises(LooperError):
            pool.push_work("late")
        with self.assertRaises(LooperError):
            pool.start_pool()
        return


if __name__ == "__main__":
    unittest.main()
