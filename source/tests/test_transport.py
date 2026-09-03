"""
    Unit tests for :mod:`ccai.rpc.core.transport`.
"""

import socket
import threading
import unittest

from ccai.rpc.errors import AbstractMethodError, ProtocolError, TransportClosedError
from ccai.rpc.core.transport import DuplexSocketIO, FaultInjectingTransport, Transport, TransportWrapper, create_socketpair_transports


class TestTransportInterface(unittest.TestCase):

    def test_abstract_methods_raise(self) -> None:
        transport = Transport()
        for call in (lambda: transport.send_frame(b"x"), transport.receive_frame, transport.close, lambda: transport.is_open):
            with self.assertRaises(AbstractMethodError):
                call()
        return

    def test_wrapper_forwards(self) -> None:
        left, right = create_socketpair_transports(receive_timeout=2)
        wrapped = TransportWrapper(left)
        try:
            wrapped.send_frame(b"via wrapper")
            self.assertEqual(right.receive_frame(), b"via wrapper")
            self.assertTrue(wrapped.is_open)
            self.assertEqual(wrapped.local_address, left.local_address)
        finally:
            wrapped.close()
            right.close()
        self.assertFalse(left.is_open)
        return


class TestDuplexSocketIO(unittest.TestCase):

    def setUp(self) -> None:
        self.left, self.right = create_socketpair_transports(receive_timeout=2)
        return

    def tearDown(self) -> None:
        self.left.close()
        self.right.close()
        return

    def test_frame_round_trip_both_directions(self) -> None:
        self.left.send_frame(b"hello")
        self.assertEqual(self.right.receive_frame(), b"hello")
        self.right.send_frame(b"back")
        self.assertEqual(self.left.receive_frame(), b"back")
        return

    def test_large_frame_spanning_many_reads(self) -> None:
        payload = bytes(range(256)) * 4096   # 1 MiB
        sender = threading.Thread(target=self.left.send_frame, args=(payload,), daemon=True)
        sender.start()
        self.assertEqual(self.right.receive_frame(), payload)
        sender.join(timeout=5)
        return

    def test_consecutive_frames_keep_boundaries(self) -> None:
        self.left.send_frame(b"one")
        self.left.send_frame(b"two")
        self.assertEqual(self.right.receive_frame(), b"one")
        self.assertEqual(self.right.receive_frame(), b"two")
        return

    def test_peer_close_mid_frame_raises_with_counts(self) -> None:
        raw = self.left.sock
        raw.sendall((10).to_bytes(8, "big") + b"abc")
        self.left.close()
        with self.assertRaises(TransportClosedError) as caught:
            self.right.receive_frame()
        self.assertIn("expected 10 bytes, received 3", str(caught.exception))
        self.assertFalse(self.right.is_open)
        return

    def test_oversized_frame_rejected(self) -> None:
        small = DuplexSocketIO(self.right.sock, receive_timeout=2, max_message_size=4)
        self.left.send_frame(b"toolong")
        with self.assertRaises(ProtocolError):
            small.receive_frame()
        return

    def test_receive_timeout_keeps_partial_data(self) -> None:
        short = DuplexSocketIO(self.right.sock, receive_timeout=0.1)
        self.left.sock.sendall((5).to_bytes(8, "big") + b"he")
        with self.assertRaises(TimeoutError):
            short.receive_frame()
        self.left.sock.sendall(b"llo")
        self.assertEqual(short.receive_frame(), b"hello")
        return

    def test_closed_transport_raises(self) -> None:
        self.left.close()
        with self.assertRaises(TransportClosedError):
            self.left.send_frame(b"x")
        with self.assertRaises(TransportClosedError):
            self.left.receive_frame()
        return

    def test_close_after_peer_close_releases_the_socket(self) -> None:
        self.left.close()
        with self.assertRaises(TransportClosedError):
            self.right.receive_frame()          # marks the transport closed on the error path
        self.assertFalse(self.right.is_open)
        self.right.close()                      # must still release the descriptor
        self.assertEqual(self.right.sock.fileno(), -1)
        return

    def test_addresses_are_tuples(self) -> None:
        self.assertIsInstance(self.left.local_address, tuple)
        self.assertEqual(len(self.left.remote_address), 2)
        return


class TestFaultInjection(unittest.TestCase):

    def setUp(self) -> None:
        self.left, self.right = create_socketpair_transports(receive_timeout=1)
        self.faulty = FaultInjectingTransport(self.left)
        return

    def tearDown(self) -> None:
        self.faulty.close()
        self.right.close()
        return

    def test_drop(self) -> None:
        self.faulty.drop_next(1)
        self.faulty.send_frame(b"lost")
        self.faulty.send_frame(b"kept")
        self.assertEqual(self.right.receive_frame(), b"kept")
        self.assertEqual(self.faulty.actions, ["dropped"])
        return

    def test_truncate(self) -> None:
        self.faulty.truncate_next()
        self.faulty.send_frame(b"0123456789")
        self.assertEqual(self.right.receive_frame(), b"01234")
        self.assertIn("truncated", self.faulty.actions)
        return

    def test_close_after(self) -> None:
        self.faulty.close_after(1)
        self.faulty.send_frame(b"last")
        self.assertEqual(self.right.receive_frame(), b"last")
        self.assertFalse(self.faulty.is_open)
        self.assertIn("closed", self.faulty.actions)
        return

    def test_delay_recorded(self) -> None:
        self.faulty.delay_frames(0.01)
        self.faulty.send_frame(b"slow")
        self.assertEqual(self.right.receive_frame(), b"slow")
        self.assertTrue(any(a.startswith("delayed") for a in self.faulty.actions))
        return


if __name__ == "__main__":
    unittest.main()
