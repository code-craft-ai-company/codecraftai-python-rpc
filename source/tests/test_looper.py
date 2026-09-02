"""
    Unit tests for :mod:`ccai.rpc.core.looper`.
"""

import threading
import unittest

from ccai.rpc.errors import AbstractMethodError, LooperError
from ccai.rpc.core.looper import Looper
from ccai.rpc.core.looperqueue import LooperQueue, LooperQueueShutdown


class RecordingLooper(Looper):

    def __init__(self, queue, name=None, group=None, daemon=None, **kwargs):
        super().__init__(queue, name=name, group=group, daemon=daemon, **kwargs)
        self.processed = []
        self.seen = threading.Event()
        return

    def loop(self, packet) -> None:
        if packet == "boom":
            raise ValueError("boom")
        self.processed.append(packet)
        self.seen.set()
        return


class TestLooperGuards(unittest.TestCase):

    def test_loop_must_be_overloaded(self) -> None:
        with self.assertRaises(AbstractMethodError):
            Looper(LooperQueue()).loop("packet")
        return

    def test_wait_for_exit_before_start_raises(self) -> None:
        with self.assertRaises(LooperError):
            Looper(LooperQueue()).wait_for_exit(timeout=0.01)
        return

    def test_double_start_raises(self) -> None:
        queue = LooperQueue()
        looper = RecordingLooper(queue, name="dup", daemon=True)
        looper.start()
        try:
            with self.assertRaises(LooperError):
                looper.start()
        finally:
            queue.shutdown(1)
            looper.wait_for_exit(timeout=2)
        return


class TestLooperProcessing(unittest.TestCase):

    def setUp(self) -> None:
        self.queue = LooperQueue()
        self.looper = RecordingLooper(self.queue, name="test-looper", group="tests", daemon=True)
        self.looper.start()
        return

    def tearDown(self) -> None:
        self.queue.shutdown(1)
        self.assertTrue(self.looper.wait_for_exit(timeout=2))
        self.assertFalse(self.looper.is_running)
        return

    def test_start_returns_running_named_thread(self) -> None:
        self.assertTrue(self.looper.is_running)
        self.assertEqual(self.looper.name, "test-looper")
        self.assertEqual(self.looper.group, "tests")
        return

    def test_processes_pushed_packet(self) -> None:
        self.queue.push_work("hello")
        self.assertTrue(self.looper.seen.wait(timeout=2))
        self.assertEqual(self.looper.processed, ["hello"])
        return

    def test_raising_loop_keeps_thread_alive(self) -> None:
        with self.assertLogs("ccai.rpc.dispatch", level="ERROR"):
            self.queue.push_work("boom")
            self.queue.push_work("after")
            self.assertTrue(self.looper.seen.wait(timeout=2))
        self.assertEqual(self.looper.processed, ["after"])
        self.assertTrue(self.looper.is_running)
        return


class TestLooperExit(unittest.TestCase):

    def test_sentinel_sets_exit_gate(self) -> None:
        queue = LooperQueue()
        looper = RecordingLooper(queue, daemon=True)
        looper.start()
        queue.push_work(LooperQueueShutdown())
        self.assertTrue(looper.wait_for_exit(timeout=2))
        return

    def test_stop_then_packet_exits(self) -> None:
        queue = LooperQueue()
        looper = RecordingLooper(queue, daemon=True)
        looper.start()
        looper.stop()
        queue.push_work("wake")
        self.assertTrue(looper.wait_for_exit(timeout=2))
        self.assertEqual(looper.processed, [])
        return


if __name__ == "__main__":
    unittest.main()
