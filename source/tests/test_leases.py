"""
    Tests for reference leases, renewal and lapse callbacks.
"""

import time
import unittest

from ccai.rpc.errors import LeaseExpiredError

from helpers import FAST, Listener, SessionPair


class TestLeases(unittest.TestCase):

    def test_live_proxy_survives_several_durations(self) -> None:
        aspects = FAST.replace(lease_duration=0.4, heartbeat_interval=0.1)
        with SessionPair(aspects=aspects) as pair:
            helper = pair.proxy().get_helper()
            time.sleep(1.0)
            self.assertEqual(helper.double(2), 4)
        return

    def test_paused_renewal_expires_reference_with_message(self) -> None:
        aspects = FAST.replace(lease_duration=0.4, heartbeat_interval=0.1)
        with SessionPair(aspects=aspects) as pair:
            helper = pair.proxy().get_helper()
            pair.client._heartbeat.stop()          # the holder stops renewing
            time.sleep(0.7)
            pair.server.sweep_leases()
            with self.assertRaises(LeaseExpiredError) as caught:
                helper.double(2)
            self.assertIn("Helper", str(caught.exception))
        return

    def test_lapse_callbacks_and_lease_aware_object(self) -> None:
        aspects = FAST.replace(lease_duration=0.4, heartbeat_interval=0.1)
        lapsed = []
        with SessionPair(aspects=aspects) as pair:
            pair.server.on_lease_lapse(lambda ref_id, obj, peer: lapsed.append((type(obj).__name__, peer)))
            listener = Listener()
            svc = pair.proxy()
            svc.register(listener)
            server_side_proxy = pair.service.listener
            # the server holds a proxy to the client's listener; stop the server renewing and let the client sweep
            pair.server._heartbeat.stop()
            time.sleep(0.7)
            pair.client.sweep_leases()
            deadline = time.monotonic() + 2
            while not any(isinstance(e, tuple) and e[0] == "lapsed" for e in listener.events) and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(any(isinstance(e, tuple) and e[0] == "lapsed" for e in listener.events), listener.events)
        return

    def test_unknown_id_in_renewal_marks_proxy_expired(self) -> None:
        aspects = FAST.replace(lease_duration=0.4, heartbeat_interval=0.1)
        with SessionPair(aspects=aspects) as pair:
            helper = pair.proxy().get_helper()
            pair.server.table.release(helper.rpc_reference_id, pair.client.session_id)
            deadline = time.monotonic() + 2
            while not helper.rpc_expired and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertTrue(helper.rpc_expired)
            with self.assertRaises(LeaseExpiredError):
                helper.double(1)
        return

    def test_session_close_lapses_peer_references(self) -> None:
        lapsed = []
        with SessionPair() as pair:
            pair.server.on_lease_lapse(lambda ref_id, obj, peer: lapsed.append(type(obj).__name__))
            helper = pair.proxy().get_helper()
            pair.client.close()
            deadline = time.monotonic() + 2
            while "Helper" not in lapsed and time.monotonic() < deadline:
                time.sleep(0.02)
            self.assertIn("Helper", lapsed)
        return

    def test_root_never_expires(self) -> None:
        aspects = FAST.replace(lease_duration=0.4, heartbeat_interval=0.1)
        with SessionPair(aspects=aspects) as pair:
            svc = pair.proxy()
            pair.client._heartbeat.stop()
            time.sleep(0.7)
            pair.server.sweep_leases()
            self.assertEqual(svc.add(1, 1), 2)
        return


if __name__ == "__main__":
    unittest.main()
