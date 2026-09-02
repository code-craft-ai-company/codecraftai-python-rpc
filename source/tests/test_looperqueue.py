"""
    Unit tests for :mod:`ccai.rpc.core.looperqueue`.
"""

import threading
import unittest

from ccai.rpc.errors import LooperError
from ccai.rpc.core.looperqueue import LooperQueue, LooperQueueShutdown


class TestLooperQueuePush(unittest.TestCase):

    def setUp(self) -> None:
        self.queue = LooperQueue()
        return

    def test_push_work_returns_depth(self) -> None:
        self.assertEqual(self.queue.push_work("a"), 1)
        self.assertEqual(self.queue.push_work("b"), 2)
        self.assertEqual(self.queue.depth, 2)
        return

    def test_push_work_packets_returns_depth(self) -> None:
        self.assertEqual(self.queue.push_work_packets(["a", "b", "c"]), 3)
        return

    def test_push_work_packets_signals_once_per_packet(self) -> None:
        self.queue.push_work_packets(["a", "b", "c"])
        popped = [self.queue.pop(timeout=0.5) for _ in range(3)]
        self.assertEqual(popped, ["a", "b", "c"])
        return


class TestLooperQueuePop(unittest.TestCase):

    def setUp(self) -> None:
        self.queue = LooperQueue()
        return

    def test_pop_is_fifo(self) -> None:
        for item in ("first", "second", "third"):
            self.queue.push_work(item)
        self.assertEqual([self.queue.pop(), self.queue.pop(), self.queue.pop()], ["first", "second", "third"])
        return

    def test_timed_pop_returns_none_when_empty(self) -> None:
        self.assertIsNone(self.queue.pop(timeout=0.05))
        return

    def test_blocking_pop_wakes_on_push(self) -> None:
        result = []
        thread = threading.Thread(target=lambda: result.append(self.queue.pop()), daemon=True)
        thread.start()
        self.queue.push_work("late")
        thread.join(timeout=2)
        self.assertEqual(result, ["late"])
        return


class TestLooperQueueShutdown(unittest.TestCase):

    def setUp(self) -> None:
        self.queue = LooperQueue()
        return

    def test_push_after_shutdown_raises(self) -> None:
        self.queue.shutdown(1)
        with self.assertRaises(LooperError):
            self.queue.push_work("late")
        with self.assertRaises(LooperError):
            self.queue.push_work_packets(["late"])
        return

    def test_shutdown_queues_one_sentinel_per_worker_after_pending_work(self) -> None:
        self.queue.push_work("pending")
        self.queue.shutdown(2)
        self.assertEqual(self.queue.pop(timeout=0.5), "pending")
        self.assertIsInstance(self.queue.pop(timeout=0.5), LooperQueueShutdown)
        self.assertIsInstance(self.queue.pop(timeout=0.5), LooperQueueShutdown)
        self.assertIsNone(self.queue.pop(timeout=0.05))
        self.assertTrue(self.queue.is_shutdown)
        return


if __name__ == "__main__":
    unittest.main()
