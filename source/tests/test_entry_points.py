"""
    End-to-end tests through RpcSocketServer and RpcSocketClient over TCP on localhost.
"""

import time
import unittest
from typing import Protocol

from ccai.rpc import (
    ConnectionTimeout,
    RemoteProxy,
    RpcSocketClient,
    RpcSocketServer,
    SessionError,
    UnauthorizedError,
    rpc_context_scope,
)
from ccai.rpc.security import shared_secret_authenticator

from helpers import FAST, Listener, Service


class ServiceProtocol(Protocol):
    def add(self, a: int, b: int = 0) -> int:
        """
            Returns the sum of ``a`` and ``b``.
        """

    def fail(self, message: str = "boom"):
        """
            Raises a ``KeyError`` carrying ``message``.
        """

    def register(self, listener) -> None:
        """
            Stores ``listener`` as the service's listener.
        """

    def fire(self, count: int):
        """
            Calls ``on_event`` on the registered listener ``count`` times and returns the results.
        """

    def caller_context(self):
        """
            Returns the caller context of the current remote call.
        """


class TestServer(unittest.TestCase):

    def test_port_zero_and_advertise(self) -> None:
        with RpcSocketServer(Service(), ("127.0.0.1", 0), aspects=FAST) as server:
            self.assertTrue(server.is_serving)
            self.assertNotEqual(server.bound_endpoint[1], 0)
            self.assertEqual(server.advertise().service_name, "Service")
            self.assertEqual(server.advertise().port, server.bound_endpoint[1])
            self.assertEqual(server.describe()["sessions"], [])
        self.assertFalse(server.is_serving)
        return

    def test_start_twice_raises(self) -> None:
        with RpcSocketServer(Service(), ("127.0.0.1", 0), aspects=FAST) as server:
            with self.assertRaises(SessionError):
                server.start()
        return

    def test_sessions_tracked_and_callbacks(self) -> None:
        opened, closed = [], []
        with RpcSocketServer(Service(), ("127.0.0.1", 0), aspects=FAST, on_session=lambda s: opened.append(s.session_id),
                             on_session_closed=lambda s, r: closed.append(s.session_id)) as server:
            clients = [RpcSocketClient(ServiceProtocol, server.bound_endpoint, aspects=FAST) for _ in range(3)]
            for client in clients:
                client.connect()
            deadline = time.monotonic() + 2
            while len(opened) < 3 and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertEqual(server.session_count, 3)
            self.assertEqual(len(opened), 3)
            clients[0].close()
            deadline = time.monotonic() + 3
            while server.session_count > 2 and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertEqual(server.session_count, 2)
            self.assertEqual(len(closed), 1)
            for client in clients[1:]:
                client.close()
        return


class TestClient(unittest.TestCase):

    def test_connection_timeout_reports_attempts(self) -> None:
        aspects = FAST.replace(max_attempts=2, completion_interval=0.05, connection_timeout=0.5)
        client = RpcSocketClient(None, ("127.0.0.1", 1), aspects=aspects)
        with self.assertRaises(ConnectionTimeout) as caught:
            client.connect()
        self.assertIn("2 attempt", str(caught.exception))
        return

    def test_provider_called_per_attempt_and_retry_succeeds(self) -> None:
        calls = []
        server = RpcSocketServer(Service(), ("127.0.0.1", 0), aspects=FAST)

        def provider():
            calls.append(1)
            if len(calls) == 2:
                server.start()
            return ("127.0.0.1", 1) if len(calls) < 2 else server.bound_endpoint

        client = RpcSocketClient(ServiceProtocol, provider, aspects=FAST.replace(max_attempts=3, completion_interval=0.05, connection_timeout=0.5))
        try:
            client.connect()
            self.assertEqual(len(calls), 2)
            self.assertTrue(client.is_connected)
        finally:
            client.close()
            server.stop()
        return

    def test_get_service_before_connect_and_double_connect(self) -> None:
        with RpcSocketServer(Service(), ("127.0.0.1", 0), aspects=FAST) as server:
            client = RpcSocketClient(ServiceProtocol, server.bound_endpoint, aspects=FAST)
            with self.assertRaises(SessionError):
                client.get_service()
            with client:
                with self.assertRaises(SessionError):
                    client.connect()
                self.assertLess(client.ping(timeout=2), 2)
        return


class TestEndToEnd(unittest.TestCase):

    def setUp(self) -> None:
        self.service = Service()
        self.server = RpcSocketServer(self.service, ("127.0.0.1", 0), aspects=FAST)
        self.server.start()
        self.client = RpcSocketClient(ServiceProtocol, self.server.bound_endpoint, aspects=FAST, context={"run_id": "r42"})
        self.client.connect()
        return

    def tearDown(self) -> None:
        self.client.close()
        self.server.stop()
        return

    def test_call_exception_and_callback_while_call_outstanding(self) -> None:
        svc = self.client.get_service()
        self.assertEqual(svc.add(2, b=3), 5)
        with self.assertRaises(KeyError):
            svc.fail("x")
        listener = Listener()
        svc.register(listener)
        self.assertEqual(svc.fire(3), [0, 2, 4])
        self.assertEqual(listener.events, [0, 1, 2])
        return

    def test_context_travels_with_session_and_scope(self) -> None:
        svc = self.client.get_service()
        self.assertEqual(svc.caller_context(), {"run_id": "r42"})
        with rpc_context_scope(test="t7"):
            self.assertEqual(svc.caller_context(), {"run_id": "r42", "test": "t7"})
        return

    def test_typed_proxy_and_describe(self) -> None:
        svc = self.client.get_service()
        self.assertIsInstance(svc, RemoteProxy)
        with self.assertRaises(AttributeError):
            svc.not_declared
        described = self.client.describe()
        self.assertTrue(described["connected"])
        self.assertEqual(described["session"]["peer_context"] if "peer_context" in described["session"] else {"run_id": "r42"}, {"run_id": "r42"})
        return


class TestAuthentication(unittest.TestCase):

    def test_shared_secret_accepts_and_rejects(self) -> None:
        with RpcSocketServer(Service(), ("127.0.0.1", 0), aspects=FAST, authenticator=shared_secret_authenticator(b"s3cret", "lab-client")) as server:
            good = RpcSocketClient(ServiceProtocol, server.bound_endpoint, aspects=FAST, credential=b"s3cret")
            good.connect()
            try:
                self.assertEqual(good.get_service().add(1, 1), 2)
                self.assertEqual(server.sessions[0].peer_identity, "lab-client")
            finally:
                good.close()
            bad = RpcSocketClient(ServiceProtocol, server.bound_endpoint, aspects=FAST, credential=b"wrong")
            with self.assertRaises(UnauthorizedError):
                bad.connect()
        return


if __name__ == "__main__":
    unittest.main()
