"""
    Tests for AspectsRpc, per-call overrides and deadline propagation.
"""

import unittest

from ccai.aspects.aspects import Aspects
from ccai.errors.exceptions import SemanticError

from ccai.rpc.aspects import AspectsRpc, DEFAULT_RPC_ASPECTS, LoggingPattern, current_aspects_override, rpc_aspects_scope
from ccai.rpc.errors import CompletionTimeout
from ccai.rpc.core.serialization import decode, encode

from helpers import FAST, SessionPair


class TestAspectsRpc(unittest.TestCase):

    def test_defaults(self) -> None:
        a = DEFAULT_RPC_ASPECTS
        self.assertIsInstance(a, Aspects)
        self.assertEqual((a.connection_timeout, a.completion_timeout, a.max_attempts), (30.0, 600.0, 1))
        self.assertEqual((a.heartbeat_interval, a.inactivity_timeout, a.lease_duration), (10.0, 60.0, 90.0))
        self.assertEqual((a.dispatch_min_workers, a.dispatch_max_workers, a.dispatch_highwater), (2, 8, 4))
        self.assertEqual(a.logging_pattern, LoggingPattern.FAILURE_ONLY)
        return

    def test_immutable(self) -> None:
        with self.assertRaises(AttributeError):
            DEFAULT_RPC_ASPECTS.completion_timeout = 1
        return

    def test_validation(self) -> None:
        for bad in ({"completion_timeout": 0}, {"max_attempts": 0}, {"dispatch_min_workers": 3, "dispatch_max_workers": 2},
                    {"lease_duration": 5, "heartbeat_interval": 10}, {"heartbeat_interval": -1}):
            with self.subTest(bad=bad), self.assertRaises(SemanticError):
                AspectsRpc(**bad)
        return

    def test_replace_and_flatten(self) -> None:
        changed = DEFAULT_RPC_ASPECTS.replace(completion_timeout=5, logging_pattern=LoggingPattern.ALL_RESULTS)
        self.assertEqual(changed.completion_timeout, 5)
        self.assertEqual(DEFAULT_RPC_ASPECTS.completion_timeout, 600.0)
        back = decode(encode(changed))
        self.assertEqual(back.completion_timeout, 5)
        self.assertEqual(back.logging_pattern, LoggingPattern.ALL_RESULTS)
        with self.assertRaises(SemanticError):
            DEFAULT_RPC_ASPECTS.replace(bogus=1)
        return

    def test_scope_is_thread_local_and_nested(self) -> None:
        self.assertIsNone(current_aspects_override())
        with rpc_aspects_scope(FAST):
            self.assertIs(current_aspects_override(), FAST)
        self.assertIsNone(current_aspects_override())
        return


class TestOverrides(unittest.TestCase):

    def setUp(self) -> None:
        self.pair = SessionPair().start()
        self.svc = self.pair.proxy()
        return

    def tearDown(self) -> None:
        self.pair.close()
        return

    def test_view_with_short_timeout_raises_while_default_succeeds(self) -> None:
        short = self.svc.rpc_with_aspects(FAST.replace(completion_timeout=0.1))
        with self.assertRaises(CompletionTimeout):
            short.sleep(0.5)
        self.assertEqual(self.svc.sleep(0.05), "slept")
        self.assertEqual(short, self.svc)
        self.assertEqual(hash(short), hash(self.svc))
        return

    def test_scope_applies_within_block_only(self) -> None:
        with rpc_aspects_scope(FAST.replace(completion_timeout=0.1)):
            with self.assertRaises(CompletionTimeout):
                self.svc.sleep(0.5)
        self.assertEqual(self.svc.sleep(0.05), "slept")
        return

    def test_deadline_reaches_the_service(self) -> None:
        remaining = self.svc.rpc_with_aspects(FAST.replace(completion_timeout=2.0)).remaining()
        self.assertIsNotNone(remaining)
        self.assertLess(remaining, 2.0)
        self.assertGreater(remaining, 1.0)
        return

    def test_session_pool_sized_from_aspects(self) -> None:
        described = self.pair.server.describe()["pool"]
        self.assertEqual(described["min_loopers"], FAST.dispatch_min_workers)
        self.assertEqual(described["max_loopers"], FAST.dispatch_max_workers)
        return


if __name__ == "__main__":
    unittest.main()
