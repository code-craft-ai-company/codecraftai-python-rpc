"""
    Unit tests for :mod:`ccai.rpc.core.looperqueue` covering push and pop ordering.
"""

import unittest

from ccai.rpc.core.looperqueue import LooperQueue


class TestLooperQueuePush(unittest.TestCase):
    """
        Verify pushing work reports the queue depth.
    """

    def setUp(self) -> None:
        self.queue = LooperQueue()
        return

    def test_push_work_returns_depth(self) -> None:
        self.assertEqual(self.queue.push_work("a"), 1)
        self.assertEqual(self.queue.push_work("b"), 2)
        return

    def test_push_work_packets_returns_depth(self) -> None:
        depth = self.queue.push_work_packets(["a", "b", "c"])
        self.assertEqual(depth, 3)
        return


class TestLooperQueuePop(unittest.TestCase):
    """
        Verify popping returns packets first-in, first-out.
    """

    def setUp(self) -> None:
        self.queue = LooperQueue()
        return

    def test_pop_returns_first_pushed(self) -> None:
        self.queue.push_work("first")
        self.queue.push_work("second")
        self.assertEqual(self.queue.pop(), "first")
        return

    def test_pop_preserves_order_across_packets_push(self) -> None:
        self.queue.push_work("first")
        self.queue.push_work("second")
        self.queue.push_work("third")
        popped = [self.queue.pop(), self.queue.pop(), self.queue.pop()]
        self.assertEqual(popped, ["first", "second", "third"])
        return


if __name__ == "__main__":
    unittest.main()
