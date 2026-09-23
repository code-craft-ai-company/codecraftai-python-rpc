"""
    Tests for callback dispatch: thread guarantees, ordering, re-entrancy and delivery modes.
"""

import threading
import time
import unittest

from ccai.rpc.errors import CompletionTimeout
from ccai.rpc.core.dispatch.context import current_call_context
from ccai.rpc.core.dispatch.lanes import LaneTable, TargetLane

from helpers import FAST, ConcurrentListener, Listener, SessionPair


class TestLanes(unittest.TestCase):

    def test_lane_serialises_work_in_order(self) -> None:
        lane = TargetLane()
        order = []
        gate = threading.Event()

        def first():
            gate.wait(timeout=2)
            order.append(1)

        thread = threading.Thread(target=lane.run, args=(first,), daemon=True)
        thread.start()
        time.sleep(0.05)
        lane.run(lambda: order.append(2))          # queued behind the running holder, returns at once
        self.assertEqual(order, [])
        gate.set()
        thread.join(timeout=2)
        self.assertEqual(order, [1, 2])
        self.assertFalse(lane.busy)
        return

    def test_lane_table_reuses_lanes(self) -> None:
        table = LaneTable()
        self.assertIs(table.get("a"), table.get("a"))
        table.discard("a")
        return


class TestCallbackThreads(unittest.TestCase):

    def setUp(self) -> None:
        self.pair = SessionPair().start()
        self.svc = self.pair.proxy()
        self.listener = Listener()
        self.svc.register(self.listener)
        return

    def tearDown(self) -> None:
        self.pair.close()
        return

    def test_callbacks_run_on_client_dispatch_threads_while_call_is_outstanding(self) -> None:
        self.assertEqual(self.svc.fire(3), [0, 2, 4])
        self.assertEqual(self.listener.events, [0, 1, 2])
        short = self.pair.client.session_id.hex[:8]
        self.assertTrue(all(name.startswith("rpc-client-dispatch-" + short) for name in self.listener.threads), self.listener.threads)
        return

    def test_callbacks_on_one_target_arrive_in_order(self) -> None:
        self.svc.fire_notify(20)
        deadline = time.monotonic() + 3
        while len(self.listener.events) < 20 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(self.listener.events, list(range(20)))
        return

    def test_concurrent_listener_may_interleave(self) -> None:
        listener = ConcurrentListener()
        self.svc.register(listener)
        self.svc.fire_notify(10)
        deadline = time.monotonic() + 3
        while len(listener.events) < 10 and time.monotonic() < deadline:
            time.sleep(0.01)
        self.assertEqual(sorted(listener.events), list(range(10)))
        return

    def test_reentrant_chain_completes(self) -> None:
        self.assertEqual(self.svc.call_back_then_query(self.listener), 42)
        return

    def test_notify_returns_before_listener_runs(self) -> None:
        # Service.fire_notify calls rpc_notify on the server-side proxy of this listener.  The listener is held at
        # 'release' until the test sets it, so fire_notify can only return here if rpc_notify did not wait for the
        # listener to run.  A notify that waited would hold the call past completion_timeout and fail the test.
        release = threading.Event()
        started = threading.Event()
        finished = threading.Event()

        class GatedListener(Listener):
            def on_event(self, i):
                started.set()
                release.wait(timeout=10)
                result = super().on_event(i)
                finished.set()
                return result
        from ccai.rpc.core.proxy.wrappers import by_ref
        by_ref(GatedListener)
        listener = GatedListener()
        self.svc.register(listener)

        try:
            self.svc.fire_notify(1)
            self.assertFalse(finished.is_set(), "rpc_notify returned only after the listener had run")
            self.assertTrue(started.wait(timeout=3), "the notified listener was never invoked")
            self.assertEqual(listener.events, [])
        finally:
            release.set()

        self.assertTrue(finished.wait(timeout=3), "the notified listener did not complete after being released")
        self.assertEqual(listener.events, [0])
        return

    def test_call_context_visible_inside_callback(self) -> None:
        seen = {}

        class ContextListener(Listener):
            def on_event(self, i):
                seen["context"] = current_call_context()
                return i
        from ccai.rpc.core.proxy.wrappers import by_ref
        by_ref(ContextListener)
        self.svc.register(ContextListener())
        self.svc.fire(1)
        self.assertIsNotNone(seen["context"])
        self.assertEqual(seen["context"].callable_name, "on_event")
        self.assertEqual(seen["context"].caller_session_id, self.pair.server.session_id)
        self.assertIsNone(current_call_context())
        return

    def test_exhausted_pools_time_out_with_diagnosis(self) -> None:
        aspects = FAST.replace(dispatch_min_workers=1, dispatch_max_workers=1, dispatch_highwater=1000, completion_timeout=0.5)
        pair = SessionPair(aspects=aspects).start()
        try:
            svc = pair.proxy()
            listener = Listener()
            svc.register(listener)

            class Blocking(Listener):
                def on_event(self, i):
                    return svc.sleep(0.05)      # nested call from the single client worker while the single server worker is busy
            from ccai.rpc.core.proxy.wrappers import by_ref
            svc.register(by_ref(Blocking)())
            with self.assertRaises(CompletionTimeout) as caught:
                svc.fire(1)
            self.assertIn("dispatch pool", str(caught.exception))
        finally:
            pair.close()
        return


if __name__ == "__main__":
    unittest.main()
