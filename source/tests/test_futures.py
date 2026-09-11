"""
    Tests for asynchronous calls, cancellation and progress.
"""

import threading
import time
import unittest

from ccai.errors.exceptions import SemanticError

from ccai.rpc.errors import CancelledError, CompletionTimeout, SessionClosedError
from ccai.rpc.core.dispatch.context import report_progress
from ccai.rpc.core.futures import RemoteFuture, as_completed, wait_all

from helpers import FAST, SessionPair


class TestFutures(unittest.TestCase):

    def setUp(self) -> None:
        self.pair = SessionPair().start()
        self.svc = self.pair.proxy()
        return

    def tearDown(self) -> None:
        self.pair.close()
        return

    def test_async_call_returns_immediately_and_resolves(self) -> None:
        started = time.monotonic()
        future = self.svc.rpc_call_async("sleep", 0.2)
        self.assertLess(time.monotonic() - started, 0.15)
        self.assertIsInstance(future, RemoteFuture)
        self.assertFalse(future.done())
        self.assertEqual(future.result(timeout=2), "slept")
        self.assertTrue(future.done())
        self.assertEqual(future.callable_name, "sleep")
        return

    def test_exception_and_done_callbacks(self) -> None:
        seen = []
        future = self.svc.rpc_call_async("fail", "bad")
        future.add_done_callback(lambda f: seen.append(f.exception()))
        self.assertIsInstance(future.exception(timeout=2), KeyError)
        deadline = time.monotonic() + 2
        while not seen and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertIsInstance(seen[0], KeyError)
        with self.assertRaises(KeyError):
            future.result()
        return

    def test_helpers_wait_all_and_as_completed(self) -> None:
        futures = [self.svc.rpc_call_async("add", i, 1) for i in range(4)]
        self.assertTrue(wait_all(futures, timeout=3))
        self.assertEqual(sorted(f.result() for f in as_completed(futures, timeout=1)), [1, 2, 3, 4])
        return

    def test_result_timeout(self) -> None:
        future = self.svc.rpc_call_async("sleep", 0.5)
        with self.assertRaises(CompletionTimeout):
            future.result(timeout=0.05)
        future.result(timeout=2)
        return

    def test_session_close_fails_outstanding_future(self) -> None:
        future = self.svc.rpc_call_async("sleep", 2)
        time.sleep(0.1)
        self.pair.client.close()
        with self.assertRaises(SessionClosedError):
            future.result(timeout=2)
        return


class TestCancellation(unittest.TestCase):

    def setUp(self) -> None:
        self.pair = SessionPair().start()
        self.svc = self.pair.proxy()
        return

    def tearDown(self) -> None:
        self.pair.close()
        return

    def test_cooperative_cancel_stops_loop_and_yields_cancelled(self) -> None:
        future = self.svc.rpc_call_async("slow_loop", 50, 0.05)
        time.sleep(0.15)
        self.assertTrue(future.cancel())
        with self.assertRaises(CancelledError):
            future.result(timeout=3)
        self.assertTrue(future.cancelled())
        self.assertFalse(future.cancel())
        return

    def test_sync_timeout_sends_cancel(self) -> None:
        before = self.pair.server.counters["requests_received"]
        # The client's completion timeout and the deadline the service enforces
        # are the same instant, so either side can win the race: a local
        # CompletionTimeout, or the service's own CancelledError reply.
        with self.assertRaises((CompletionTimeout, CancelledError)):
            self.svc.rpc_with_aspects(FAST.replace(completion_timeout=0.2)).slow_loop(50, 0.05)
        time.sleep(0.2)
        # a CANCEL request reached the server on top of the call itself
        self.assertGreaterEqual(self.pair.server.counters["requests_received"] - before, 2)
        return

    def test_deadline_observed_as_cancelled_and_remaining_time(self) -> None:
        remaining = self.svc.remaining()
        self.assertIsNotNone(remaining)
        self.assertLessEqual(remaining, FAST.completion_timeout)
        return

    def test_expired_deadline_not_invoked(self) -> None:
        from ccai.rpc.core.protocol.messages import RequestCall
        from ccai.rpc.core.proxy.table import ROOT_REFERENCE_ID
        with self.assertRaises(CancelledError):
            self.pair.client.send_request(RequestCall(target_ref=ROOT_REFERENCE_ID, callable_name="add", args=(1, 1), kwargs={}, deadline=-1.0, context={}), timeout=2)
        return


class TestProgress(unittest.TestCase):

    def setUp(self) -> None:
        self.pair = SessionPair().start()
        self.svc = self.pair.proxy()
        return

    def tearDown(self) -> None:
        self.pair.close()
        return

    def test_progress_callbacks_on_dispatch_thread(self) -> None:
        future = self.svc.rpc_call_async("slow_loop", 4, 0.02)
        seen = []
        future.add_progress_callback(lambda p: seen.append((p.fraction, threading.current_thread().name)))
        self.assertEqual(future.result(timeout=3), "finished")
        deadline = time.monotonic() + 1
        while len(seen) < 4 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual([round(f, 2) for f, _ in seen], [0.25, 0.5, 0.75, 1.0])
        self.assertTrue(all(name.startswith("rpc-client-dispatch-") for _, name in seen))
        self.assertEqual(future.last_progress.details, {"step": 4})
        return

    def test_report_progress_outside_call_raises(self) -> None:
        with self.assertRaises(SemanticError):
            report_progress(0.5)
        return


if __name__ == "__main__":
    unittest.main()
