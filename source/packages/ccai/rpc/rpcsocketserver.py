"""
.. module:: rpcsocketserver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RpcSocketServer, which exposes a service object on an endpoint with one session per connection.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Callable, Dict, Optional, Tuple

import logging
import socket
import threading
import uuid

from ccai.rpc.aspects import AspectsRpc, DEFAULT_RPC_ASPECTS
from ccai.rpc.endpoints import Endpoint, ServiceEndpoint
from ccai.rpc.errors import SessionError
from ccai.rpc.core.protocol.constants import DEFAULT_MAX_MESSAGE_SIZE
from ccai.rpc.core.session.server import DuplexServerSession
from ccai.rpc.core.transport.base import Transport
from ccai.rpc.core.transport.socketio import DuplexSocketIO

Authenticator = Callable[[bytes, Tuple[str, int]], Optional[str]]

_live_servers = set()


class RpcSocketServer:

    def __init__(self, service: object, endpoint: Endpoint, backlog: int = 16, aspects: AspectsRpc = DEFAULT_RPC_ASPECTS,
                 upgrader: Optional[Callable[[Transport], None]] = None, authenticator: Optional[Authenticator] = None,
                 on_session: Optional[Callable[[DuplexServerSession], None]] = None,
                 on_session_closed: Optional[Callable[[DuplexServerSession, BaseException], None]] = None,
                 service_name: Optional[str] = None, max_message_size: int = DEFAULT_MAX_MESSAGE_SIZE) -> None:
        self._service = service
        self._endpoint = (endpoint[0], int(endpoint[1]))
        self._backlog = backlog
        self._aspects = aspects
        self._upgrader = upgrader
        self._authenticator = authenticator
        self._on_session = on_session
        self._on_session_closed = on_session_closed
        self._service_name = service_name or type(service).__name__
        self._max_message_size = max_message_size
        self._listen_sock: Optional[socket.socket] = None
        self._bound: Optional[Endpoint] = None
        self._sessions: Dict[uuid.UUID, DuplexServerSession] = {}
        self._lock = threading.RLock()
        self._serving = False
        self._accept_thread: Optional[threading.Thread] = None
        self._listening = threading.Event()
        self.logger = logging.getLogger("ccai.rpc.server")
        return

    # ------------------------------------------------------------------ properties
    @property
    def service(self) -> object:
        return self._service

    @property
    def endpoint(self) -> Endpoint:
        return self._endpoint

    @property
    def bound_endpoint(self) -> Optional[Endpoint]:
        return self._bound

    @property
    def aspects(self) -> AspectsRpc:
        return self._aspects

    @property
    def is_serving(self) -> bool:
        return self._serving

    @property
    def session_count(self) -> int:
        with self._lock:
            return len(self._sessions)

    @property
    def sessions(self):
        with self._lock:
            return list(self._sessions.values())

    # ------------------------------------------------------------------ lifecycle
    def _bind(self) -> None:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            sock.bind(self._endpoint)
        except OSError as err:
            sock.close()
            raise OSError("could not bind RPC server to {}:{}: {}".format(self._endpoint[0], self._endpoint[1], err)) from err
        sock.listen(self._backlog)
        self._listen_sock = sock
        self._bound = sock.getsockname()[:2]
        self._serving = True
        _live_servers.add(self)
        self._listening.set()
        self.logger.info("serving %s on %s", self._service_name, self._bound)
        return

    def start(self) -> None:
        with self._lock:
            if self._serving:
                raise SessionError("server is already serving")
            self._listening.clear()
        self._bind()
        self._accept_thread = threading.Thread(target=self._accept_loop, name="rpc-server-accept-{}".format(self._bound[1]), daemon=True)
        self._accept_thread.start()
        return

    def serve_forever(self) -> None:
        with self._lock:
            if self._serving:
                raise SessionError("server is already serving")
        self._bind()
        self._accept_loop()
        return

    def _accept_loop(self) -> None:
        while self._serving:
            try:
                client_sock, addr = self._listen_sock.accept()
            except OSError:
                break
            try:
                self._accept(client_sock, addr)
            except Exception:  # noqa: BLE001
                self.logger.exception("failed to start a session for %s", addr)
                try:
                    client_sock.close()
                except OSError:
                    pass
        return

    def _accept(self, client_sock: socket.socket, addr) -> None:
        transport = DuplexSocketIO(client_sock, receive_timeout=0.5, max_message_size=self._max_message_size)
        if self._upgrader is not None:
            self._upgrader(transport)
        session = DuplexServerSession(transport, aspects=self._aspects, service=self._service, authenticator=self._authenticator,
                                      on_closed=self._session_closed, on_hello=self._session_ready)
        with self._lock:
            self._sessions[session.session_id] = session
        session.start()
        return

    def _session_ready(self, session: DuplexServerSession) -> None:
        if self._on_session is not None:
            try:
                self._on_session(session)
            except Exception:  # noqa: BLE001
                self.logger.exception("on_session callback raised")
        return

    def _session_closed(self, session: DuplexServerSession, reason: BaseException) -> None:
        with self._lock:
            self._sessions.pop(session.session_id, None)
        if self._on_session_closed is not None:
            try:
                self._on_session_closed(session, reason)
            except Exception:  # noqa: BLE001
                self.logger.exception("on_session_closed callback raised")
        return

    def stop(self, timeout: Optional[float] = 5.0) -> int:
        with self._lock:
            if not self._serving:
                return 0
            self._serving = False
            sessions = list(self._sessions.values())
        if self._listen_sock is not None:
            try:
                self._listen_sock.shutdown(socket.SHUT_RDWR)
            except OSError:
                pass
            if self._accept_thread is not None and self._accept_thread.is_alive() and self._bound is not None:
                # a blocked accept() does not always wake on close; a throwaway connection guarantees it
                try:
                    socket.create_connection(("127.0.0.1" if self._bound[0] in ("0.0.0.0", "") else self._bound[0], self._bound[1]), timeout=0.5).close()
                except OSError:
                    pass
            try:
                self._listen_sock.close()
            except OSError:
                pass
        for session in sessions:
            try:
                session.close(timeout=timeout)
            except Exception:  # noqa: BLE001
                self.logger.exception("closing session %s failed", session.session_id)
        if self._accept_thread is not None and self._accept_thread is not threading.current_thread():
            self._accept_thread.join(timeout=timeout)
        _live_servers.discard(self)
        self.logger.info("stopped %s on %s, closed %d session(s)", self._service_name, self._bound, len(sessions))
        return len(sessions)

    def __enter__(self) -> "RpcSocketServer":
        self.start()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.stop()
        return None

    # ------------------------------------------------------------------ diagnostics
    def advertise(self) -> ServiceEndpoint:
        host, port = self._bound if self._bound is not None else self._endpoint
        return ServiceEndpoint(host=host, port=port, service_name=self._service_name)

    def describe(self) -> dict:
        return {"service": self._service_name, "endpoint": self._endpoint, "bound": self._bound, "serving": self._serving,
                "sessions": [s.describe() for s in self.sessions]}
