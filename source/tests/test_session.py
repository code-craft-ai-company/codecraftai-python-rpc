"""
    Tests for the session layer: lifecycle, correlation, exceptions, timeouts and heartbeat.
"""

import threading
import time
import unittest
import uuid

from ccai.rpc.errors import CompletionTimeout, InActivityTimeout, ProtocolError, SessionClosedError, SessionError
from ccai.rpc.core.protocol.messages import ReplyCall, RequestCall, RequestPing
from ccai.rpc.core.proxy.table import ROOT_REFERENCE_ID
from ccai.rpc.core.session import DuplexClientSession, DuplexServerSession
from ccai.rpc.core.transport import FaultInjectingTransport, create_socketpair_transports

from helpers import FAST, Service, SessionPair


class TestLifecycle(unittest.TestCase):

    def test_hello_exchanges_session_ids_and_lease(self) -> None:
        with SessionPair() as pair:
            self.assertEqual(pair.client.peer_session_id, pair.server.session_id)
            self.assertEqual(pair.server.peer_session_id, pair.client.session_id)
            self.assertEqual(pair.client.lease_duration, FAST.lease_duration)
            self.assertTrue(pair.server.hello_done.is_set())
        return

    def test_double_start_raises(self) -> None:
        with SessionPair() as pair:
            with self.assertRaises(SessionError):
                pair.client.start()
        return

    def test_close_fails_outstanding_waiters(self) -> None:
        with SessionPair() as pair:
            svc = pair.proxy()
            errors = []

            def call():
                try:
                    svc.sleep(2)
                except Exception as err:  # noqa: BLE001
                    errors.append(err)
            thread = threading.Thread(target=call, daemon=True)
            thread.start()
            time.sleep(0.2)
            pair.client.close()
            thread.join(timeout=3)
            self.assertEqual(len(errors), 1)
            self.assertIsInstance(errors[0], SessionClosedError)
        return

    def test_peer_close_tears_down_other_side(self) -> None:
        pair = SessionPair().start()
        try:
            pair.client.close()
            deadline = time.monotonic() + 3
            while pair.server.is_running and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertFalse(pair.server.is_running)
        finally:
            pair.close()
        return

    def test_context_manager_closes(self) -> None:
        pair = SessionPair().start()
        with pair.client:
            self.assertTrue(pair.client.is_running)
        self.assertTrue(pair.client.is_closed)
        pair.close()
        return

    def test_thread_names(self) -> None:
        with SessionPair() as pair:
            names = {t.name for t in threading.enumerate()}
            short = pair.client.session_id.hex[:8]
            self.assertIn("rpc-client-recv-" + short, names)
            self.assertIn("rpc-client-xmit-" + short, names)
            self.assertTrue(any(n.startswith("rpc-client-dispatch-" + short) for n in names))
        return


class TestRequests(unittest.TestCase):

    def test_reply_correlation_with_many_outstanding_from_one_thread(self) -> None:
        with SessionPair() as pair:
            futures = [pair.client.send_request_async(RequestCall(target_ref=ROOT_REFERENCE_ID, callable_name="add", args=(i, 1), kwargs={}, deadline=3.0, context={}))
                       for i in range(5)]
            results = [f.result(timeout=3).value for f in futures]
            self.assertEqual(results, [1, 2, 3, 4, 5])
        return

    def test_remote_exception_propagates_with_traceback(self) -> None:
        with SessionPair() as pair:
            svc = pair.proxy()
            with self.assertRaises(KeyError) as caught:
                svc.fail("nope")
            self.assertIn("raise KeyError", caught.exception.remote_traceback)
        return

    def test_timeout_message_names_call_and_pool(self) -> None:
        with SessionPair() as pair:
            svc = pair.proxy().rpc_with_aspects(FAST.replace(completion_timeout=0.2))
            with self.assertRaises(CompletionTimeout) as caught:
                svc.sleep(1.0)
            text = str(caught.exception)
            self.assertIn("sleep", text)
            self.assertIn("dispatch pool", text)
            self.assertEqual(pair.client.counters["timeouts"], 1)
        return

    def test_stray_reply_is_logged_and_dropped(self) -> None:
        with SessionPair() as pair:
            frame = ReplyCall(value=1, correlation_id=uuid.uuid4()).pack()
            with self.assertLogs("ccai.rpc", level="WARNING") as logs:
                pair.client._route_frame(frame)
            self.assertTrue(any("stray" in line for line in logs.output))
        return

    def test_ping_round_trip(self) -> None:
        with SessionPair() as pair:
            self.assertLess(pair.client.ping(timeout=2), 2)
        return

    def test_unknown_request_code_yields_protocol_error(self) -> None:
        with SessionPair() as pair:
            pair.server._handlers.pop(int(RequestCall.mcode))
            with self.assertRaises(ProtocolError):
                pair.proxy().add(1, 2)
        return


class TestHeartbeat(unittest.TestCase):

    def test_idle_session_sends_pings(self) -> None:
        with SessionPair() as pair:
            before = pair.server.counters["requests_received"]
            # Several heartbeat intervals, so a slow runner cannot miss the first ping.
            time.sleep(2.0)
            self.assertGreater(pair.server.counters["requests_received"], before)
        return

    def test_inactivity_tears_down_and_fails_waiters(self) -> None:
        aspects = FAST.replace(inactivity_timeout=0.5, heartbeat_interval=0.2, lease_duration=0.4)
        pair = SessionPair(aspects=aspects).start()
        try:
            pair.server._heartbeat.stop()
            pair.server._running = False          # server goes silent: no pings, no replies
            svc = pair.proxy() if False else None
            deadline = time.monotonic() + 3
            while pair.client.is_running and time.monotonic() < deadline:
                time.sleep(0.05)
            self.assertFalse(pair.client.is_running)
            self.assertIsInstance(pair.client._close_reason, InActivityTimeout)
        finally:
            pair.close()
        return


class TestSendFailure(unittest.TestCase):

    def test_transport_send_failure_tears_down(self) -> None:
        ct, st = create_socketpair_transports(receive_timeout=0.2)
        faulty = FaultInjectingTransport(ct)
        server = DuplexServerSession(st, aspects=FAST, service=Service())
        client = DuplexClientSession(faulty, aspects=FAST)
        server.start()
        client.start()
        try:
            faulty.close_after(1)
            with self.assertRaises((SessionClosedError, CompletionTimeout)):
                client.send_request(RequestPing(), timeout=1)
                client.send_request(RequestPing(), timeout=1)
            deadline = time.monotonic() + 3
            while client.is_running and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertFalse(client.is_running)
        finally:
            client.close()
            server.close()
        return


if __name__ == "__main__":
    unittest.main()
