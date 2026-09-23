"""
    Tests for reference isolation, the attribute policy and TLS upgraders.
"""

import os
import ssl
import subprocess
import tempfile
import unittest

from ccai.rpc import RpcSocketClient, RpcSocketServer, UnknownReferenceError, expose_private, mutable_service
from ccai.rpc.core.proxy.remoteproxy import RemoteProxy
from ccai.rpc.security import tls_client_upgrader, tls_server_upgrader

from helpers import FAST, Service, SessionPair


class TestIsolation(unittest.TestCase):

    def test_reference_from_another_session_refused(self) -> None:
        with SessionPair() as first, SessionPair(service=first.service) as second:
            helper = first.proxy().get_helper()
            stolen = RemoteProxy(second.client, helper.rpc_reference_id, second.server.session_id, "Helper")
            with self.assertRaises(UnknownReferenceError):
                stolen.double(2)
            self.assertEqual(helper.double(2), 4)
        return

    def test_private_refused_unless_exposed(self) -> None:
        @expose_private
        class Open(Service):
            pass
        with SessionPair() as closed_pair, SessionPair(service=Open()) as open_pair:
            with self.assertRaises(AttributeError):
                closed_pair.proxy()._secret
            self.assertEqual(open_pair.proxy()._secret, "hidden")
        return

    def test_root_writes_refused_unless_mutable(self) -> None:
        @mutable_service
        class Mutable(Service):
            pass
        with SessionPair() as fixed, SessionPair(service=Mutable()) as mutable:
            with self.assertRaises(AttributeError):
                fixed.proxy().value = 9
            mutable.proxy().value = 9
            self.assertEqual(mutable.service.value, 9)
        return

    def test_server_message_size_limit(self) -> None:
        from ccai.rpc.errors import SessionClosedError, CompletionTimeout
        with RpcSocketServer(Service(), ("127.0.0.1", 0), aspects=FAST.replace(completion_timeout=1.0), max_message_size=512) as server:
            client = RpcSocketClient(None, server.bound_endpoint, aspects=FAST.replace(completion_timeout=1.0))
            client.connect()
            try:
                svc = client.get_service()
                with self.assertRaises((SessionClosedError, CompletionTimeout)):
                    svc.echo("x" * 2000)
            finally:
                client.close()
        return


def _make_cert(directory: str):
    key = os.path.join(directory, "key.pem")
    cert = os.path.join(directory, "cert.pem")
    result = subprocess.run(["openssl", "req", "-x509", "-newkey", "rsa:2048", "-nodes", "-keyout", key, "-out", cert, "-days", "1",
                             "-subj", "/CN=localhost", "-addext", "subjectAltName=DNS:localhost,IP:127.0.0.1"], capture_output=True)
    return (key, cert) if result.returncode == 0 else (None, None)


class TestTls(unittest.TestCase):

    def test_tls_round_trip_and_verification_failure(self) -> None:
        with tempfile.TemporaryDirectory() as directory:
            key, cert = _make_cert(directory)
            if key is None:
                self.skipTest("openssl not available")
            server_ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER)
            server_ctx.load_cert_chain(cert, key)
            with RpcSocketServer(Service(), ("127.0.0.1", 0), aspects=FAST, upgrader=tls_server_upgrader(server_ctx)) as server:
                trusting = ssl.create_default_context(cafile=cert)
                client = RpcSocketClient(None, server.bound_endpoint, aspects=FAST, upgrader=tls_client_upgrader(trusting, "localhost"))
                client.connect()
                try:
                    self.assertEqual(client.get_service().add(3, 4), 7)
                finally:
                    client.close()
                distrusting = ssl.create_default_context()
                strict = RpcSocketClient(None, server.bound_endpoint, aspects=FAST.replace(max_attempts=1), upgrader=tls_client_upgrader(distrusting, "localhost"))
                with self.assertRaises(Exception):
                    strict.connect()
        return


if __name__ == "__main__":
    unittest.main()
