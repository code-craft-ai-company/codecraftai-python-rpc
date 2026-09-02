"""
.. module:: rpcsocketclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RpcSocketClient, which connects to a service with retry and returns a typed proxy to it.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Callable, Dict, Generic, Optional, Type, TypeVar, Union

import logging
import socket
import time

from ccai.rpc.aspects import AspectsRpc, DEFAULT_RPC_ASPECTS
from ccai.rpc.endpoints import Endpoint, EndpointProvider, resolve_endpoint
from ccai.rpc.errors import ConnectionTimeout, SessionError, UnauthorizedError
from ccai.rpc.core.protocol.constants import DEFAULT_MAX_MESSAGE_SIZE
from ccai.rpc.core.session.client import DuplexClientSession
from ccai.rpc.core.transport.base import Transport
from ccai.rpc.core.transport.socketio import DuplexSocketIO

ServiceProtocol = TypeVar("ServiceProtocol")

_live_clients = set()


class RpcSocketClient(Generic[ServiceProtocol]):

    def __init__(self, service_protocol: Optional[Type[ServiceProtocol]], endpoint: Union[Endpoint, EndpointProvider],
                 aspects: AspectsRpc = DEFAULT_RPC_ASPECTS, upgrader: Optional[Callable[[Transport], None]] = None,
                 credential: bytes = b"", context: Optional[Dict[str, str]] = None,
                 max_message_size: int = DEFAULT_MAX_MESSAGE_SIZE) -> None:
        self._service_protocol = service_protocol
        self._endpoint = endpoint
        self._aspects = aspects
        self._upgrader = upgrader
        self._credential = credential
        self._context = dict(context or {})
        self._max_message_size = max_message_size
        self._session: Optional[DuplexClientSession] = None
        self.logger = logging.getLogger("ccai.rpc.client")
        return

    @property
    def endpoint(self) -> Endpoint:
        return resolve_endpoint(self._endpoint)

    @property
    def aspects(self) -> AspectsRpc:
        return self._aspects

    @property
    def is_connected(self) -> bool:
        return self._session is not None and self._session.is_running

    @property
    def session(self) -> Optional[DuplexClientSession]:
        return self._session

    def connect(self, aspects: Optional[AspectsRpc] = None) -> None:
        if self.is_connected:
            raise SessionError("client is already connected to {}".format(self._session.remote_address))
        aspects = aspects if aspects is not None else self._aspects
        last_error = None
        endpoint = None
        for attempt in range(1, aspects.max_attempts + 1):
            endpoint = resolve_endpoint(self._endpoint)
            try:
                sock = socket.create_connection(endpoint, timeout=aspects.connection_timeout)
            except OSError as err:
                last_error = err
                self.logger.info("connect attempt %d/%d to %s failed: %s", attempt, aspects.max_attempts, endpoint, err)
                if attempt < aspects.max_attempts:
                    time.sleep(aspects.completion_interval)
                continue
            transport = DuplexSocketIO(sock, receive_timeout=0.5, max_message_size=self._max_message_size)
            if self._upgrader is not None:
                self._upgrader(transport)
            session = DuplexClientSession(transport, aspects=self._aspects, credential=self._credential, context=self._context)
            try:
                session.start(hello_timeout=aspects.connection_timeout)
            except UnauthorizedError:
                raise
            except Exception as err:  # noqa: BLE001 - retry on a failed handshake
                last_error = err
                if isinstance(err, SessionError) and "UnauthorizedError" in str(err):
                    raise UnauthorizedError(str(err)) from err
                if attempt < aspects.max_attempts:
                    time.sleep(aspects.completion_interval)
                continue
            self._session = session
            _live_clients.add(self)
            return
        raise ConnectionTimeout("could not connect to {} after {} attempt(s); last error: {}".format(endpoint, aspects.max_attempts, last_error))

    def close(self, timeout: Optional[float] = 5.0) -> None:
        if self._session is not None:
            self._session.close(timeout=timeout)
        _live_clients.discard(self)
        return

    def get_service(self, aspects: Optional[AspectsRpc] = None) -> ServiceProtocol:
        if not self.is_connected:
            raise SessionError("get_service called before connect")
        return self._session.get_service(protocol=self._service_protocol, aspects=aspects)

    def ping(self, timeout: Optional[float] = None) -> float:
        if not self.is_connected:
            raise SessionError("ping called before connect")
        return self._session.ping(timeout=timeout)

    def describe(self) -> dict:
        return {"endpoint": self.endpoint, "connected": self.is_connected, "session": self._session.describe() if self._session else None}

    def __enter__(self) -> "RpcSocketClient":
        self.connect()
        return self

    def __exit__(self, exc_type, exc, tb) -> None:
        self.close()
        return None
