"""
    Tests for object proxies: wrappers, the reference table, RemoteProxy forwarding and release.
"""

import gc
import time
import unittest
import uuid
from typing import Protocol

from ccai.rpc.errors import LeaseExpiredError, SessionClosedError, UnknownReferenceError
from ccai.rpc.core.proxy.remoteproxy import RemoteProxy
from ccai.rpc.core.proxy.table import ROOT_REFERENCE_ID, ReferenceTable
from ccai.rpc.core.proxy.wrappers import ByRef, ByValue, by_ref, is_by_ref_type

from helpers import Listener, SessionPair


class ServiceProtocol(Protocol):
    value: int

    def add(self, a: int, b: int = 0) -> int:
        """
            Returns the sum of ``a`` and ``b``.
        """

    def echo(self, *args, **kwargs):
        """
            Returns the positional and keyword arguments it was called with.
        """

    def fail(self, message: str = "boom"):
        """
            Raises a ``KeyError`` carrying ``message``.
        """

    def get_helper(self):
        """
            Returns the service's helper object.
        """


class TestWrappers(unittest.TestCase):

    def test_wrappers_expose_instance(self) -> None:
        target = object()
        self.assertIs(ByRef(target).instance, target)
        self.assertIs(ByValue(target).instance, target)
        return

    def test_by_ref_decorator(self) -> None:
        @by_ref
        class Marked:
            pass
        self.assertTrue(is_by_ref_type(Marked()))
        self.assertFalse(is_by_ref_type(object()))
        return


class TestReferenceTable(unittest.TestCase):

    def setUp(self) -> None:
        self.table = ReferenceTable()
        self.peer = uuid.uuid4()
        return

    def test_register_is_idempotent(self) -> None:
        obj = object()
        self.assertEqual(self.table.register(obj), self.table.register(obj))
        return

    def test_resolve_unknown_raises(self) -> None:
        with self.assertRaises(UnknownReferenceError):
            self.table.resolve(uuid.uuid4())
        return

    def test_holder_check_and_release(self) -> None:
        obj = object()
        ref = self.table.register(obj)
        with self.assertRaises(UnknownReferenceError):
            self.table.resolve(ref, self.peer)
        self.table.add_holder(ref, self.peer, 10)
        self.assertIs(self.table.resolve(ref, self.peer), obj)
        self.assertIs(self.table.release(ref, self.peer), obj)
        with self.assertRaises(UnknownReferenceError):
            self.table.resolve(ref, self.peer)
        # the owner can still resolve a recently released id, so a reference coming home mid-release resolves
        self.assertIs(self.table.resolve(ref), obj)
        self.assertIsNone(self.table.lookup(obj))
        return

    def test_root_is_reserved_and_exempt(self) -> None:
        root = object()
        self.table.register_root(root)
        self.assertIs(self.table.resolve(ROOT_REFERENCE_ID, self.peer), root)
        self.assertIsNone(self.table.release(ROOT_REFERENCE_ID))
        self.table.release_all()
        self.assertTrue(self.table.has_root())
        return

    def test_lease_expiry_and_renew(self) -> None:
        obj = object()
        ref = self.table.register(obj)
        self.table.add_holder(ref, self.peer, 0.05)
        time.sleep(0.08)
        with self.assertRaises(LeaseExpiredError):
            self.table.resolve(ref, self.peer)
        self.assertEqual(self.table.expired(), [(ref, self.peer)])
        self.assertEqual(self.table.renew(self.peer, [ref, uuid.uuid4()], 10)[1:], [])
        self.assertEqual(len(self.table.renew(self.peer, [uuid.uuid4()], 10)), 1)
        self.assertIs(self.table.resolve(ref, self.peer), obj)
        self.assertEqual(self.table.describe()[0]["holders"], 1)
        return


class TestRemoteProxy(unittest.TestCase):

    def setUp(self) -> None:
        self.pair = SessionPair().start()
        self.svc = self.pair.proxy(protocol=ServiceProtocol)
        return

    def tearDown(self) -> None:
        self.pair.close()
        return

    def test_method_call_is_one_round_trip(self) -> None:
        before = self.pair.client.counters["requests_sent"]
        self.assertEqual(self.svc.add(2, b=3), 5)
        self.assertEqual(self.pair.client.counters["requests_sent"] - before, 1)
        return

    def test_attribute_read(self) -> None:
        self.assertEqual(self.svc.value, 1)
        return

    def test_attribute_write_refused_on_root_without_marker(self) -> None:
        with self.assertRaises(AttributeError):
            self.svc.value = 5
        return

    def test_private_attribute_refused(self) -> None:
        untyped = self.pair.proxy()
        with self.assertRaises(AttributeError):
            untyped._secret
        return

    def test_protocol_filters_unknown_names_locally(self) -> None:
        before = self.pair.client.counters["requests_sent"]
        with self.assertRaises(AttributeError):
            self.svc.no_such_method
        self.assertEqual(self.pair.client.counters["requests_sent"], before)
        return

    def test_untyped_proxy_calls_via_method_reference(self) -> None:
        untyped = self.pair.proxy()
        self.assertEqual(untyped.add(1, 2), 3)
        return

    def test_returned_object_becomes_proxy_with_dunders(self) -> None:
        helper = self.svc.get_helper()
        self.assertIsInstance(helper, RemoteProxy)
        self.assertEqual(helper.double(4), 8)
        self.assertEqual(len(helper), 3)
        self.assertEqual(list(helper), [1, 2, 3])
        self.assertIn(2, helper)
        self.assertEqual(helper[0], 1)
        helper[0] = 10
        self.assertEqual(helper[0], 10)
        del helper[0]
        self.assertEqual(len(helper), 2)
        with helper as h:
            self.assertIs(h, helper)
        self.assertTrue(helper.entered)
        return

    def test_attribute_write_and_delete_on_non_root(self) -> None:
        helper = self.svc.get_helper()
        helper.extra = "x"
        self.assertEqual(helper.extra, "x")
        del helper.extra
        with self.assertRaises(AttributeError):
            helper.extra
        return

    def test_repr_is_local_and_equality_by_reference(self) -> None:
        before = self.pair.client.counters["requests_sent"]
        text = repr(self.svc)
        self.assertIn("Service", text)
        self.assertEqual(self.pair.client.counters["requests_sent"], before)
        other = self.pair.proxy()
        self.assertEqual(self.svc, other)
        self.assertEqual(hash(self.svc), hash(other))
        return

    def test_same_reference_yields_same_proxy_and_returns_home(self) -> None:
        untyped = self.pair.proxy()
        helper1 = untyped.get_helper()
        helper2 = untyped.get_helper()
        self.assertIs(helper1, helper2)
        self.assertTrue(untyped.same(untyped))
        return

    def test_by_value_and_by_ref_arguments(self) -> None:
        listener = Listener()
        self.assertEqual(self.svc.echo(ByValue([1, 2]), k=3), (([1, 2],), {"k": 3}))
        returned = self.pair.proxy().echo_object(listener)
        self.assertIs(returned, listener)
        return

    def test_unwrapped_object_rejected_before_send(self) -> None:
        from ccai.rpc.errors import SerializationError
        before = self.pair.client.counters["requests_sent"]
        with self.assertRaises(SerializationError):
            self.svc.echo(object())
        self.assertEqual(self.pair.client.counters["requests_sent"], before)
        return

    def test_release_and_use_after_close(self) -> None:
        helper = self.pair.proxy().get_helper()
        ref = helper.rpc_reference_id
        self.assertIn(ref, self.pair.server.table.held_by(self.pair.client.session_id))
        helper.rpc_release()
        deadline = time.monotonic() + 2
        while ref in self.pair.server.table.held_by(self.pair.client.session_id) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertNotIn(ref, self.pair.server.table.held_by(self.pair.client.session_id))
        with self.assertRaises(SessionClosedError):
            helper.double(1)
        self.pair.client.close()
        with self.assertRaises(SessionClosedError):
            self.svc.add(1, 1)
        return

    def test_garbage_collected_proxy_sends_release(self) -> None:
        helper = self.pair.proxy().get_helper()
        ref = helper.rpc_reference_id
        del helper
        gc.collect()
        deadline = time.monotonic() + 2
        while ref in self.pair.server.table.held_by(self.pair.client.session_id) and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertNotIn(ref, self.pair.server.table.held_by(self.pair.client.session_id))
        return

    def test_unknown_reference_from_peer(self) -> None:
        stale = RemoteProxy(self.pair.client, uuid.uuid4(), self.pair.server.session_id, "Nothing")
        with self.assertRaises(UnknownReferenceError):
            stale.anything
        return


if __name__ == "__main__":
    unittest.main()
