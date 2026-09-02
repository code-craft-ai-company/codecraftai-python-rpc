"""
.. module:: client
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DuplexClientSession: the session that opens with HELLO and exposes get_service.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Optional

from ccai.rpc.errors import ProtocolError, SessionError
from ccai.rpc.core.protocol.constants import MIN_SUPPORTED_VERSION, PROTOCOL_VERSION
from ccai.rpc.core.protocol.messages import RequestGetService, RequestHello, RequestPing
from ccai.rpc.core.session.base import DuplexSessionBase


class DuplexClientSession(DuplexSessionBase):

    role = "client"

    def start(self, hello_timeout: Optional[float] = None) -> None:
        super().start()
        timeout = hello_timeout if hello_timeout is not None else self._aspects.connection_timeout
        hello = RequestHello(version_min=MIN_SUPPORTED_VERSION, version_max=PROTOCOL_VERSION, session_id=self.session_id,
                             credential=self._credential, context=self._context)
        try:
            reply = self.send_request(hello, timeout=timeout)
        except BaseException as err:
            self._teardown(SessionError("HELLO failed: {}".format(err)))
            raise
        if not (MIN_SUPPORTED_VERSION <= reply.chosen_version <= PROTOCOL_VERSION):
            self._teardown(ProtocolError("server chose unsupported protocol version {}".format(reply.chosen_version)))
            raise ProtocolError("server chose unsupported protocol version {}".format(reply.chosen_version))
        self.protocol_version = reply.chosen_version
        self.peer_session_id = reply.session_id
        self.lease_duration = reply.lease_duration
        self.renewal_interval = min(self._aspects.heartbeat_interval, reply.lease_duration / 3.0)
        self.logger.extra["peer_session_id"] = str(self.peer_session_id)
        self.logger.info("HELLO complete: protocol %s, server session %s, lease %ss", self.protocol_version, self.peer_session_id, self.lease_duration)
        return

    def get_service(self, protocol: Optional[type] = None, aspects=None):
        reply = self.send_request(RequestGetService(), timeout=self.resolve_aspects(aspects).completion_timeout)
        proxy = reply.value
        if protocol is not None or aspects is not None:
            proxy = proxy.rpc_with_protocol(protocol) if protocol is not None else proxy
            proxy = proxy.rpc_with_aspects(aspects) if aspects is not None else proxy
        return proxy

    def ping(self, timeout: Optional[float] = None) -> float:
        import time
        started = time.monotonic()
        self.send_request(RequestPing(), timeout=timeout if timeout is not None else self._aspects.connection_timeout)
        return time.monotonic() - started
