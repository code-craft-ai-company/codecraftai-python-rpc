"""
.. module:: heartbeat
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The per-session timer thread: idle pings, lease renewals, dead-peer detection and lease sweeps.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

import threading
import time

from ccai.rpc.errors import InActivityTimeout
from ccai.rpc.core.protocol.messages import RequestPing, RequestRenew


class HeartbeatMonitor:

    def __init__(self, session) -> None:
        self._session = session
        self._stop = threading.Event()
        self._thread = None
        self._last_sweep = time.monotonic()
        self._warned_calls = set()
        return

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, name="rpc-{}-heartbeat-{}".format(self._session.role, self._session._short), daemon=True)
        self._thread.start()
        return

    def stop(self) -> None:
        self._stop.set()
        return

    def tick(self) -> None:
        session = self._session
        aspects = session.aspects
        now = time.monotonic()
        if not session.is_running:
            return
        if now - session.last_received_at > aspects.inactivity_timeout:
            session.logger.warning("no frame received for %.1fs, treating peer %s as dead", now - session.last_received_at, session.peer_session_id)
            threading.Thread(target=session._teardown, args=(InActivityTimeout("no frame received from peer {} for {:.1f}s".format(
                session.peer_session_id, now - session.last_received_at)),), name="rpc-{}-teardown-{}".format(session.role, session._short), daemon=True).start()
            return
        from ccai.rpc.core.proxy.table import ROOT_REFERENCE_ID
        live = [ref_id for ref_id in session.proxies.live_ids() if ref_id != ROOT_REFERENCE_ID]
        interval = min(aspects.heartbeat_interval, session.renewal_interval) if live else aspects.heartbeat_interval
        if live and now - getattr(self, "_last_renew", 0.0) >= interval:
            self._last_renew = now
            self._renew(live)
        elif now - session.last_sent_at >= aspects.heartbeat_interval:
            try:
                session.send_notification(RequestPing())
            except Exception:  # noqa: BLE001
                pass
        if now - self._last_sweep >= aspects.lease_duration / 2:
            self._last_sweep = now
            session.sweep_leases()
        for context in list(session._active_calls.values()):
            if context.elapsed > aspects.completion_timeout and context.correlation_id not in self._warned_calls:
                self._warned_calls.add(context.correlation_id)
                session.logger.warning("callback '%s' has been running for %.1fs, longer than completion_timeout", context.callable_name, context.elapsed)
        return

    def _renew(self, ref_ids) -> None:
        session = self._session
        try:
            future = session.send_request_async(RequestRenew(ref_ids=tuple(ref_ids)))
        except Exception:  # noqa: BLE001
            return

        def on_done(fut):
            try:
                reply = fut.result(timeout=0)
            except Exception:  # noqa: BLE001
                return
            for ref_id in reply.unknown:
                proxy = session.proxies.get(ref_id)
                if proxy is not None:
                    proxy.rpc_mark_expired()
        future.add_done_callback(on_done)
        return

    def _run(self) -> None:
        period = max(0.05, min(self._session.aspects.heartbeat_interval, self._session.renewal_interval) / 4)
        while not self._stop.wait(timeout=period):
            try:
                self.tick()
            except Exception:  # noqa: BLE001
                self._session.logger.exception("heartbeat tick failed")
        return
