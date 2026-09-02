"""
    Tests for logging attributes, counters, wire trace and state dumps.
"""

import logging
import unittest

from ccai.rpc import RpcSocketClient, RpcSocketServer
from ccai.rpc.core.observability import dump_state, live_clients, live_servers
from ccai.rpc.core.protocol.messages import RequestPing

from helpers import FAST, Service, SessionPair


class TestLoggingAndCounters(unittest.TestCase):

    def test_log_records_carry_session_attributes(self) -> None:
        logger = logging.getLogger("ccai.rpc")
        previous = logger.level
        logger.setLevel(logging.INFO)
        try:
            with self.assertLogs("ccai.rpc", level="INFO") as logs:
                with SessionPair() as pair:
                    pair.proxy().add(1, 1)
            record = next(r for r in logs.records if "HELLO complete" in r.getMessage())
            self.assertTrue(hasattr(record, "session_id"))
            self.assertIn(record.role, ("client", "server"))
        finally:
            logger.setLevel(previous)
        return

    def test_counters_and_metrics_sink(self) -> None:
        seen = []
        with SessionPair() as pair:
            pair.client.register_metrics_sink(lambda sid, counters: seen.append((sid, counters)))
            pair.proxy().add(1, 1)
            with self.assertRaises(KeyError):
                pair.proxy().fail()
            counters = pair.client.counters
            self.assertGreaterEqual(counters["requests_sent"], 2)
            self.assertGreaterEqual(counters["exceptions_received"], 1)
            self.assertGreater(counters["bytes_sent"], 0)
            client_id = pair.client.session_id
        self.assertEqual(seen[0][0], client_id)
        return

    def test_wire_trace_logs_frames(self) -> None:
        with SessionPair() as pair:
            with self.assertLogs("ccai.rpc.wire", level="DEBUG") as logs:
                pair.client.send_request(RequestPing(), timeout=2)
            self.assertTrue(any("REQUEST/2" in line for line in logs.output))
            self.assertTrue(any("REPLY/2" in line for line in logs.output))
        return

    def test_describe_and_dump_state(self) -> None:
        with RpcSocketServer(Service(), ("127.0.0.1", 0), aspects=FAST) as server:
            client = RpcSocketClient(None, server.bound_endpoint, aspects=FAST)
            client.connect()
            try:
                self.assertIn(server, live_servers())
                self.assertIn(client, live_clients())
                text = dump_state()
                self.assertIn("servers", text)
                self.assertIn("Service", text)
                described = client.session.describe()
                for key in ("session_id", "peer_session_id", "pool", "counters", "references", "active_calls"):
                    self.assertIn(key, described)
            finally:
                client.close()
        self.assertNotIn(server, live_servers())
        return


if __name__ == "__main__":
    unittest.main()
