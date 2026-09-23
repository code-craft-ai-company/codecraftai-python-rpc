"""
.. module:: base
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DuplexSessionBase, the object that owns one transport and its receive, transmit, heartbeat and
               dispatch threads, correlates replies to waiting callers and tears itself down cleanly.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Callable, Dict, List, Optional

import logging
import threading
import time
import uuid

from ccai.rpc.aspects import AspectsRpc, DEFAULT_RPC_ASPECTS, current_aspects_override
from ccai.rpc.errors import (
    CancelledError,
    CompletionTimeout,
    LeaseExpiredError,
    ProtocolError,
    SessionClosedError,
    SessionError,
    TransportClosedError,
    UnauthorizedError,
    UnknownReferenceError,
)
from ccai.rpc.core.dispatch.context import CallContext
from ccai.rpc.core.dispatch.lanes import LaneTable
from ccai.rpc.core.futures import Progress, RemoteFuture
from ccai.rpc.core.looperpool import LooperPool
from ccai.rpc.core.looperqueue import LooperQueue
from ccai.rpc.core.protocol.constants import HEADER_SIZE, PROTOCOL_VERSION, ExceptionCode, MessageType, RequestCode
from ccai.rpc.core.protocol.header import MessageHeader
from ccai.rpc.core.protocol.messages import (
    REPLY_FOR_REQUEST,
    ExceptionMessage,
    Message,
    ReplyPing,
    RequestCancel,
    RequestClose,
    RequestProgress,
    RequestRelease,
)
from ccai.rpc.core.proxy.cache import ProxyCache
from ccai.rpc.core.proxy.remoteproxy import RemoteProxy
from ccai.rpc.core.proxy.table import ROOT_REFERENCE_ID, ReferenceTable
from ccai.rpc.core.serialization import ReferencePlaceholder
from ccai.rpc.core.session.dispatch import DispatchLooper
from ccai.rpc.core.session.heartbeat import HeartbeatMonitor
from ccai.rpc.core.transport.base import Transport

wire_logger = logging.getLogger("ccai.rpc.wire")

_request_context = threading.local()


def rpc_context_scope(**pairs: str):
    """
        Context manager adding ``pairs`` to every request sent on this thread within the block.
    """
    import contextlib

    @contextlib.contextmanager
    def scope():
        previous = dict(getattr(_request_context, "pairs", {}))
        merged = dict(previous)
        merged.update({k: str(v) for k, v in pairs.items()})
        _request_context.pairs = merged
        try:
            yield
        finally:
            _request_context.pairs = previous
    return scope()


class Waiter:

    __slots__ = ("correlation_id", "request_code", "callable_name", "event", "frame", "failure", "on_complete", "created_at")

    def __init__(self, correlation_id: uuid.UUID, request_code: int, callable_name: str) -> None:
        self.correlation_id = correlation_id
        self.request_code = request_code
        self.callable_name = callable_name
        self.event = threading.Event()
        self.frame = None
        self.failure = None
        self.on_complete = None
        self.created_at = time.monotonic()
        return

    def complete(self, frame: bytes) -> None:
        self.frame = frame
        self.event.set()
        if self.on_complete is not None:
            self.on_complete()
        return

    def fail(self, error: BaseException) -> None:
        self.failure = error
        self.event.set()
        if self.on_complete is not None:
            self.on_complete()
        return


Handler = Callable[["DuplexSessionBase", Message, CallContext], Optional[Message]]
LapseCallback = Callable[[uuid.UUID, object, uuid.UUID], None]


class DuplexSessionBase:
    """
        Symmetric session machine. Client and server sessions differ only in the HELLO direction and their
        handler sets. The receive thread only reads frames and routes by header; every payload is decoded on
        a dispatch worker or on the caller's own thread.
    """

    role = "session"

    def __init__(self, transport: Transport, aspects: AspectsRpc = DEFAULT_RPC_ASPECTS, service: Optional[object] = None,
                 context: Optional[Dict[str, str]] = None, credential: bytes = b"", authenticator=None,
                 on_closed: Optional[Callable[["DuplexSessionBase", BaseException], None]] = None) -> None:
        self._transport = transport
        self._aspects = aspects
        self._service = service
        self._context = dict(context or {})
        self._credential = credential
        self._authenticator = authenticator
        self._on_closed = on_closed

        self.session_id = uuid.uuid4()
        self.peer_session_id: Optional[uuid.UUID] = None
        self.peer_context: Dict[str, str] = {}
        self.peer_identity: Optional[str] = None
        self.protocol_version = PROTOCOL_VERSION
        self.lease_duration = aspects.lease_duration
        self.renewal_interval = aspects.heartbeat_interval

        self._short = self.session_id.hex[:8]
        self.logger = logging.LoggerAdapter(
            logging.getLogger("ccai.rpc" + ("." + aspects.logger_name if aspects.logger_name else "")),
            {"session_id": str(self.session_id), "peer_session_id": None, "role": self.role})

        self._lock = threading.RLock()
        self._running = False
        self._closing = False
        self._closed = False
        self._close_reason: Optional[BaseException] = None
        self._waiters: Dict[uuid.UUID, Waiter] = {}
        self._quiet_replies: Dict[uuid.UUID, float] = {}     # correlation ids of notifications whose replies are dropped silently
        self._futures: Dict[uuid.UUID, RemoteFuture] = {}
        self._active_calls: Dict[uuid.UUID, CallContext] = {}
        self._handlers: Dict[int, Handler] = {}
        self._lapse_callbacks: List[LapseCallback] = []
        self._outbound = LooperQueue()
        self._pool: Optional[LooperPool] = None
        self._receive_thread: Optional[threading.Thread] = None
        self._transmit_thread: Optional[threading.Thread] = None
        self._heartbeat: Optional[HeartbeatMonitor] = None
        self._lanes = LaneTable()
        self.table = ReferenceTable()
        self.proxies = ProxyCache()
        self.last_received_at = time.monotonic()
        self.last_sent_at = time.monotonic()
        self.counters = {"requests_sent": 0, "requests_received": 0, "replies_sent": 0, "replies_received": 0,
                         "exceptions_sent": 0, "exceptions_received": 0, "timeouts": 0, "bytes_sent": 0, "bytes_received": 0}
        self._metrics_sinks: List[Callable[[uuid.UUID, dict], None]] = []
        if service is not None:
            self.table.register_root(service)
        self._install_handlers()
        return

    # ------------------------------------------------------------------ properties
    @property
    def aspects(self) -> AspectsRpc:
        return self._aspects

    @property
    def is_running(self) -> bool:
        return self._running and not self._closing

    @property
    def is_closed(self) -> bool:
        return self._closed

    @property
    def remote_address(self):
        return self._transport.remote_address

    @property
    def transport(self) -> Transport:
        return self._transport

    @property
    def service(self):
        return self._service

    # ------------------------------------------------------------------ lifecycle
    def start(self) -> None:
        with self._lock:
            if self._running or self._closed:
                raise SessionError("session {} cannot be started: it is {}".format(self._short, "already running" if self._running else "closed"))
            self._running = True
        aspects = self._aspects
        self._pool = LooperPool(DispatchLooper, group_name="rpc-{}-dispatch-{}".format(self.role, self._short),
                                min_loopers=aspects.dispatch_min_workers, max_loopers=aspects.dispatch_max_workers,
                                highwater=aspects.dispatch_highwater, daemon=True, session=self)
        self._pool.start_pool()
        self._receive_thread = self._start_thread("recv", self._receive_loop)
        self._transmit_thread = self._start_thread("xmit", self._transmit_loop)
        self._heartbeat = HeartbeatMonitor(self)
        self._heartbeat.start()
        self.logger.info("session started role=%s remote=%s", self.role, self.remote_address)
        return

    def _start_thread(self, purpose: str, target) -> threading.Thread:
        gate = threading.Event()
        thread = threading.Thread(target=target, name="rpc-{}-{}-{}".format(self.role, purpose, self._short), args=(gate,), daemon=True)
        thread.start()
        gate.wait()
        return thread

    def close(self, timeout: Optional[float] = 5.0) -> None:
        if self._closed or self._closing:
            return
        if self._running and self._transport.is_open:
            try:
                self.send_notification(RequestClose())
                time.sleep(0.02)
            except Exception:  # noqa: BLE001 - closing anyway
                pass
        self._teardown(SessionClosedError("session {} closed locally".format(self._short)), timeout=timeout)
        return

    def _teardown(self, reason: BaseException, timeout: Optional[float] = 5.0) -> None:
        with self._lock:
            if self._closing or self._closed:
                return
            self._closing = True
            self._close_reason = reason
            waiters = list(self._waiters.values())
            self._waiters.clear()
        self.logger.info("session teardown: %s", reason)
        for waiter in waiters:
            waiter.fail(reason)
        for future in list(self._futures.values()):
            pass
        self._futures.clear()
        if self._pool is not None:
            self._pool.shutdown(timeout=timeout)
        self._transport.close()
        self._outbound.shutdown(1)
        if self._heartbeat is not None:
            self._heartbeat.stop()
        current = threading.current_thread()
        for thread in (self._receive_thread, self._transmit_thread):
            if thread is not None and thread is not current:
                thread.join(timeout=timeout)
        # references held by the peer lapse with the session
        if self.peer_session_id is not None:
            self._expire_references(self.table.held_by(self.peer_session_id), self.peer_session_id, "session closed")
        for proxy in self.proxies.live_proxies():
            proxy.rpc_mark_closed()
        with self._lock:
            self._running = False
            self._closed = True
        for sink in list(self._metrics_sinks):
            try:
                sink(self.session_id, dict(self.counters))
            except Exception:  # noqa: BLE001
                self.logger.exception("metrics sink raised")
        if self._on_closed is not None:
            try:
                self._on_closed(self, reason)
            except Exception:  # noqa: BLE001
                self.logger.exception("on_closed callback raised")
        return

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
        return None

    # ------------------------------------------------------------------ sending
    def _pack(self, message: Message) -> bytes:
        return message.pack(ref_encoder=self.encode_reference, known_lookup=self.known_reference)

    def _enqueue(self, frame: bytes) -> None:
        if not self._running or self._closing:
            raise SessionClosedError("session {} is not running".format(self._short))
        self._outbound.push_work(frame)
        return

    def request_context(self) -> Dict[str, str]:
        pairs = dict(getattr(_request_context, "pairs", {}))
        return pairs

    def resolve_aspects(self, override: Optional[AspectsRpc]) -> AspectsRpc:
        if override is not None:
            return override
        scoped = current_aspects_override()
        return scoped if scoped is not None else self._aspects

    def send_request_async(self, message: Message, timeout: Optional[float] = None, unwrap: bool = False) -> RemoteFuture:
        waiter = self._register_waiter(message)
        future = RemoteFuture(self, waiter, getattr(message, "callable_name", type(message).__name__), timeout, unwrap=unwrap)
        with self._lock:
            self._futures[message.correlation_id] = future
        self._send_registered(message, waiter)
        return future

    def send_request(self, message: Message, timeout: Optional[float] = None) -> Message:
        """
            Sends ``message`` and blocks the calling thread until its reply arrives. Raises the decoded
            remote exception, or CompletionTimeout after ``timeout`` seconds.
        """
        waiter = self._register_waiter(message)
        self._send_registered(message, waiter)
        timeout = timeout if timeout is not None else self._aspects.completion_timeout
        if not waiter.event.wait(timeout=timeout):
            with self._lock:
                self._waiters.pop(waiter.correlation_id, None)
            self.counters["timeouts"] += 1
            if message.mtype == MessageType.REQUEST and message.mcode in (RequestCode.CALL, RequestCode.GETATTR, RequestCode.SETATTR, RequestCode.DELATTR):
                try:
                    self.send_cancel(message.correlation_id)
                except Exception:  # noqa: BLE001
                    pass
            raise CompletionTimeout("no reply to {} '{}' from session {} within {}s (elapsed {:.2f}s); {}".format(
                RequestCode(message.mcode).name, waiter.callable_name, self.peer_session_id, timeout,
                time.monotonic() - waiter.created_at, self._pool_summary()))
        return self.resolve_reply(waiter)

    def _register_waiter(self, message: Message) -> Waiter:
        name = getattr(message, "callable_name", None) or getattr(message, "name", None) or type(message).__name__
        waiter = Waiter(message.correlation_id, int(message.mcode), str(name))
        with self._lock:
            if not self._running or self._closing:
                raise SessionClosedError("session {} is not running".format(self._short))
            self._waiters[message.correlation_id] = waiter
        return waiter

    def _send_registered(self, message: Message, waiter: Waiter) -> None:
        try:
            frame = self._pack(message)
            self._enqueue(frame)
        except BaseException:
            with self._lock:
                self._waiters.pop(waiter.correlation_id, None)
            raise
        self.counters["requests_sent"] += 1
        return

    def resolve_reply(self, waiter: Waiter) -> Message:
        """
            Decodes a completed waiter's frame on the caller's thread, raising remote exceptions.
        """
        if waiter.failure is not None:
            raise waiter.failure
        reply = Message.unpack(waiter.frame, resolver=self.resolve_reference)
        if reply.mtype == MessageType.EXCEPTION:
            self.counters["exceptions_received"] += 1
            raise self._exception_from_message(reply)
        self.counters["replies_received"] += 1
        expected = REPLY_FOR_REQUEST.get(waiter.request_code)
        if expected is not None and type(reply) is not expected:
            raise ProtocolError("reply {} does not answer request {}".format(type(reply).__name__, RequestCode(waiter.request_code).name))
        return reply

    def _exception_from_message(self, message: ExceptionMessage) -> BaseException:
        code = ExceptionCode(message.code) if message.code in ExceptionCode._value2member_map_ else ExceptionCode.REMOTE_EXCEPTION
        if code == ExceptionCode.REMOTE_EXCEPTION and isinstance(message.value, BaseException):
            return message.value
        text = message.message or message.type_name
        mapping = {ExceptionCode.PROTOCOL_ERROR: ProtocolError, ExceptionCode.UNKNOWN_REFERENCE: UnknownReferenceError,
                   ExceptionCode.LEASE_EXPIRED: LeaseExpiredError, ExceptionCode.CANCELLED: CancelledError,
                   ExceptionCode.UNAUTHORIZED: UnauthorizedError}
        exc = mapping.get(code, type(message.value) if isinstance(message.value, BaseException) else RuntimeError)(text)
        try:
            exc.remote_traceback = message.traceback_text
        except Exception:  # noqa: BLE001
            pass
        return exc

    def send_notification(self, message: Message) -> None:
        with self._lock:
            now = time.monotonic()
            if len(self._quiet_replies) > 512:
                for cid, stamp in list(self._quiet_replies.items()):
                    if now - stamp > self._aspects.completion_timeout:
                        self._quiet_replies.pop(cid, None)
            self._quiet_replies[message.correlation_id] = now
        self._enqueue(self._pack(message))
        self.counters["requests_sent"] += 1
        return

    def send_reply(self, reply: Message) -> None:
        self._enqueue(self._pack(reply))
        self.counters["replies_sent"] += 1
        return

    def send_exception(self, exception_message: ExceptionMessage) -> None:
        self._enqueue(self._pack(exception_message))
        self.counters["exceptions_sent"] += 1
        return

    def send_cancel(self, target_correlation_id: uuid.UUID) -> None:
        self.send_notification(RequestCancel(target_correlation_id=target_correlation_id))
        return

    def send_progress(self, target_correlation_id: uuid.UUID, fraction: float, message: Optional[str], details: dict) -> None:
        self.send_notification(RequestProgress(target_correlation_id=target_correlation_id, fraction=fraction, message=message, details=details))
        return

    def release_reference(self, ref_id: uuid.UUID) -> None:
        self.proxies.forget(ref_id)
        if self.is_running:
            try:
                self.send_notification(RequestRelease(ref_id=ref_id))
            except SessionClosedError:
                # The session closed after the is_running check; the owning side drops every reference
                # held by a closed session, so there is nothing left to release.
                pass
        return

    # ------------------------------------------------------------------ references
    def encode_reference(self, obj: object) -> Optional[ReferencePlaceholder]:
        if isinstance(obj, RemoteProxy):
            return ReferencePlaceholder(obj.rpc_reference_id, obj.rpc_owner_session_id, obj.rpc_remote_type_name)
        ref_id = self.table.register(obj)
        if self.peer_session_id is not None and ref_id != ROOT_REFERENCE_ID:
            self.table.add_holder(ref_id, self.peer_session_id, self.lease_duration)
        return ReferencePlaceholder(ref_id, self.session_id, type(obj).__name__)

    def known_reference(self, obj: object) -> Optional[ReferencePlaceholder]:
        ref_id = self.table.lookup(obj)
        if ref_id is None:
            return None
        if self.peer_session_id is not None and ref_id != ROOT_REFERENCE_ID:
            self.table.add_holder(ref_id, self.peer_session_id, self.lease_duration)
        return ReferencePlaceholder(ref_id, self.session_id, type(obj).__name__)

    def resolve_reference(self, placeholder: ReferencePlaceholder) -> object:
        if placeholder.session_id == self.session_id:
            return self.table.resolve(placeholder.ref_id)
        proxy = self.proxies.get(placeholder.ref_id)
        if proxy is None:
            proxy = RemoteProxy(self, placeholder.ref_id, placeholder.session_id, placeholder.type_name)
            self.proxies.put(placeholder.ref_id, proxy)
            import weakref
            weakref.finalize(proxy, self._proxy_collected, placeholder.ref_id)
        return proxy

    def _proxy_collected(self, ref_id: uuid.UUID) -> None:
        if self.proxies.get(ref_id) is None and self.is_running:
            try:
                self.send_notification(RequestRelease(ref_id=ref_id))
            except Exception:  # noqa: BLE001
                pass
            self.proxies.forget(ref_id)
        return

    def on_lease_lapse(self, callback: LapseCallback) -> None:
        self._lapse_callbacks.append(callback)
        return

    def _expire_references(self, ref_ids, peer: uuid.UUID, why: str) -> None:
        for ref_id in ref_ids:
            obj = self.table.release(ref_id, peer)
            if obj is None:
                continue
            log = self.logger.info if why == "session closed" else self.logger.warning
            log("reference %s (%s) held by %s lapsed: %s", ref_id, type(obj).__name__, peer, why)
            self._fire_lapse(ref_id, obj, peer)
        return

    def _fire_lapse(self, ref_id: uuid.UUID, obj: object, peer: uuid.UUID) -> None:
        def work():
            handler = getattr(obj, "on_lease_lapsed", None)
            if callable(handler):
                try:
                    handler(peer)
                except Exception:  # noqa: BLE001
                    self.logger.exception("on_lease_lapsed on %s raised", type(obj).__name__)
            for callback in list(self._lapse_callbacks):
                try:
                    callback(ref_id, obj, peer)
                except Exception:  # noqa: BLE001
                    self.logger.exception("lease lapse callback raised")
        if self._pool is not None and self._pool.is_running:
            self._pool.push_work(work)
        else:
            work()
        return

    def sweep_leases(self) -> None:
        expired = self.table.expired()
        for ref_id, peer in expired:
            self._expire_references([ref_id], peer, "lease expired")
        return

    # ------------------------------------------------------------------ handlers
    def register_handler(self, code: RequestCode, handler: Handler) -> None:
        self._handlers[int(code)] = handler
        return

    def _install_handlers(self) -> None:
        from ccai.rpc.core.proxy.handlers import install as install_proxy_handlers
        install_proxy_handlers(self)
        self.register_handler(RequestCode.CLOSE, self._handle_close)
        self.register_handler(RequestCode.RELEASE, self._handle_release)
        self.register_handler(RequestCode.RENEW, self._handle_renew)
        self.register_handler(RequestCode.CANCEL, self._handle_cancel)
        self.register_handler(RequestCode.PROGRESS, self._handle_progress)
        return

    def _handle_close(self, session, message, context):
        self.logger.info("peer %s requested close", self.peer_session_id)
        threading.Thread(target=self._teardown, args=(SessionClosedError("peer {} closed the session".format(self.peer_session_id)),),
                         name="rpc-{}-close-{}".format(self.role, self._short), daemon=True).start()
        return None

    def _handle_release(self, session, message, context):
        self.table.release(message.ref_id, self.peer_session_id)
        from ccai.rpc.core.protocol.messages import ReplyRelease
        return ReplyRelease()

    def _handle_renew(self, session, message, context):
        from ccai.rpc.core.protocol.messages import ReplyRenew
        unknown = self.table.renew(self.peer_session_id, list(message.ref_ids), self.lease_duration)
        return ReplyRenew(unknown=tuple(unknown))

    def _handle_cancel(self, session, message, context):
        with self._lock:
            target = self._active_calls.get(message.target_correlation_id)
        if target is not None:
            target.cancel()
        return None

    def _handle_progress(self, session, message, context):
        with self._lock:
            future = self._futures.get(message.target_correlation_id)
        if future is not None:
            future._deliver_progress(Progress(message.fraction, message.message, dict(message.details or {}), message.target_correlation_id))
        return None

    def handler_for(self, code: int) -> Optional[Handler]:
        return self._handlers.get(code)

    def track_call(self, context: CallContext) -> None:
        with self._lock:
            self._active_calls[context.correlation_id] = context
        return

    def untrack_call(self, context: CallContext) -> None:
        with self._lock:
            self._active_calls.pop(context.correlation_id, None)
        return

    def lane_for(self, target_ref: Optional[uuid.UUID]):
        return self._lanes.get(target_ref) if target_ref is not None else None

    # ------------------------------------------------------------------ threads
    def _receive_loop(self, gate: threading.Event) -> None:
        gate.set()
        reason = None
        while self._running and not self._closing:
            try:
                frame = self._transport.receive_frame()
            except TimeoutError:
                continue
            except TransportClosedError as err:
                reason = err
                break
            except Exception as err:  # noqa: BLE001
                self.logger.exception("receive thread failed")
                reason = err
                break
            try:
                self._route_frame(frame)
            except ProtocolError as err:
                self.logger.warning("discarding malformed frame: %s", err)
            except Exception:  # noqa: BLE001
                self.logger.exception("failed to route frame")
        if reason is not None and not self._closing:
            threading.Thread(target=self._teardown, args=(SessionClosedError("transport closed: {}".format(reason)),),
                             name="rpc-{}-teardown-{}".format(self.role, self._short), daemon=True).start()
        return

    def _route_frame(self, frame: bytes) -> None:
        header = MessageHeader.unpack(frame)
        if header.payload_length != len(frame) - HEADER_SIZE:
            raise ProtocolError("frame length does not match its header")
        self.last_received_at = time.monotonic()
        self.counters["bytes_received"] += len(frame)
        if wire_logger.isEnabledFor(logging.DEBUG):
            wire_logger.debug("%s <- %s/%s cid=%s payload=%d", self._short, header.mtype.name, header.mcode, header.correlation_id.hex[:8], header.payload_length)
        if header.mtype in (MessageType.REPLY, MessageType.EXCEPTION):
            with self._lock:
                waiter = self._waiters.pop(header.correlation_id, None)
                quiet = self._quiet_replies.pop(header.correlation_id, None) is not None
            if waiter is None:
                if not quiet:
                    self.logger.warning("discarding stray %s for unknown correlation id %s", header.mtype.name, header.correlation_id)
                return
            waiter.complete(frame)
            return
        self.counters["requests_received"] += 1
        if header.mcode == RequestCode.PING:
            self.send_reply(ReplyPing(correlation_id=header.correlation_id))
            return
        if header.mcode == RequestCode.HELLO:
            self._handle_hello_frame(frame, header)
            return
        self._pool.push_work(frame)
        return

    def _handle_hello_frame(self, frame: bytes, header: MessageHeader) -> None:
        raise ProtocolError("unexpected HELLO on a {} session".format(self.role))

    def _transmit_loop(self, gate: threading.Event) -> None:
        gate.set()
        from ccai.rpc.core.looperqueue import LooperQueueShutdown
        while True:
            frame = self._outbound.pop()
            if frame is None or isinstance(frame, LooperQueueShutdown):
                break
            try:
                self._transport.send_frame(frame)
                self.last_sent_at = time.monotonic()
                self.counters["bytes_sent"] += len(frame)
                if wire_logger.isEnabledFor(logging.DEBUG):
                    header = MessageHeader.unpack(frame)
                    wire_logger.debug("%s -> %s/%s cid=%s payload=%d", self._short, header.mtype.name, header.mcode, header.correlation_id.hex[:8], header.payload_length)
            except TransportClosedError as err:
                if not self._closing:
                    threading.Thread(target=self._teardown, args=(SessionClosedError("send failed: {}".format(err)),),
                                     name="rpc-{}-teardown-{}".format(self.role, self._short), daemon=True).start()
                break
        return

    # ------------------------------------------------------------------ diagnostics
    def register_metrics_sink(self, sink: Callable[[uuid.UUID, dict], None]) -> None:
        self._metrics_sinks.append(sink)
        return

    def _pool_summary(self) -> str:
        if self._pool is None:
            return "dispatch pool not started"
        described = self._pool.describe()
        busy = sum(1 for ctx in list(self._active_calls.values()))
        return "dispatch pool {}: {} workers, {} busy, {} queued".format(described["group"], described["worker_count"], busy, described["queue_depth"])

    def describe(self) -> dict:
        with self._lock:
            active = [ctx.describe() for ctx in self._active_calls.values()]
            waiters = len(self._waiters)
        return {
            "role": self.role, "session_id": str(self.session_id), "peer_session_id": str(self.peer_session_id) if self.peer_session_id else None,
            "peer_identity": self.peer_identity, "running": self.is_running, "closed": self._closed, "protocol_version": self.protocol_version,
            "remote": self.remote_address, "outstanding_requests": waiters, "outbound_depth": self._outbound.depth,
            "active_calls": active, "pool": self._pool.describe() if self._pool else None, "references": self.table.describe(),
            "live_proxies": len(self.proxies.live_ids()), "last_received_ago": round(time.monotonic() - self.last_received_at, 3),
            "last_sent_ago": round(time.monotonic() - self.last_sent_at, 3), "counters": dict(self.counters),
        }

    def __repr__(self) -> str:
        return "<{} {} peer={} running={}>".format(type(self).__name__, self._short, self.peer_session_id, self.is_running)
