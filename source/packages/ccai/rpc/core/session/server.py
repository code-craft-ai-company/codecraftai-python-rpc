"""
.. module:: server
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DuplexServerSession: the session that answers HELLO, authenticating the peer first.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

import threading

from ccai.rpc.errors import ProtocolError, UnauthorizedError
from ccai.rpc.core.protocol.constants import MIN_SUPPORTED_VERSION, PROTOCOL_VERSION, ExceptionCode
from ccai.rpc.core.protocol.messages import ExceptionMessage, Message, ReplyHello
from ccai.rpc.core.session.base import DuplexSessionBase


class DuplexServerSession(DuplexSessionBase):

    role = "server"

    def __init__(self, *args, on_hello=None, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._on_hello = on_hello
        self.hello_done = threading.Event()
        return

    def _handle_hello_frame(self, frame: bytes, header) -> None:
        message = Message.unpack(frame)
        chosen = min(message.version_max, PROTOCOL_VERSION)
        if chosen < max(message.version_min, MIN_SUPPORTED_VERSION):
            self.send_exception(ExceptionMessage(code=int(ExceptionCode.PROTOCOL_ERROR), type_name="ProtocolError",
                                                 message="no common protocol version", correlation_id=header.correlation_id))
            threading.Thread(target=self._teardown, args=(ProtocolError("no common protocol version with peer"),), daemon=True).start()
            return
        if self._authenticator is not None:
            identity = None
            try:
                identity = self._authenticator(message.credential or b"", self.remote_address)
            except Exception as err:  # noqa: BLE001
                self.logger.warning("authentication raised for %s: %s", self.remote_address, err)
            if identity is None:
                self.logger.warning("authentication failed for %s", self.remote_address)
                self.send_exception(ExceptionMessage(code=int(ExceptionCode.UNAUTHORIZED), type_name="UnauthorizedError",
                                                     message="credential rejected", correlation_id=header.correlation_id))
                import time
                time.sleep(0.05)
                threading.Thread(target=self._teardown, args=(UnauthorizedError("peer {} failed authentication".format(self.remote_address)),), daemon=True).start()
                return
            self.peer_identity = identity
            self.logger.info("authenticated %s as %s", self.remote_address, identity)
        elif getattr(self._transport, "peer_identity", None):
            self.peer_identity = getattr(self._transport, "peer_identity")
            self.logger.info("authenticated %s by client certificate as %s", self.remote_address, self.peer_identity)
        self.protocol_version = chosen
        self.peer_session_id = message.session_id
        self.peer_context = dict(message.context or {})
        self.logger.extra["peer_session_id"] = str(self.peer_session_id)
        self.send_reply(ReplyHello(chosen_version=chosen, session_id=self.session_id, lease_duration=self._aspects.lease_duration,
                                   heartbeat_interval=self._aspects.heartbeat_interval, correlation_id=header.correlation_id))
        self.hello_done.set()
        self.logger.info("HELLO complete: protocol %s, client session %s", chosen, self.peer_session_id)
        if self._on_hello is not None:
            self._pool.push_work(lambda: self._on_hello(self))
        return
