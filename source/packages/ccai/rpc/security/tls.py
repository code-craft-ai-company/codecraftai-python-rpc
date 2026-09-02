"""
.. module:: tls
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Transport upgraders that wrap a connected socket in TLS before any frame is exchanged.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Callable

import socket
import ssl

from ccai.rpc.core.transport.base import Transport


def tls_server_upgrader(context: ssl.SSLContext) -> Callable[[Transport], None]:
    def upgrade(transport: Transport) -> None:
        transport.upgrade(lambda sock: context.wrap_socket(sock, server_side=True))
    return upgrade


def tls_client_upgrader(context: ssl.SSLContext, server_hostname: str, verify: bool = True) -> Callable[[Transport], None]:
    if not verify:
        context.check_hostname = False
        context.verify_mode = ssl.CERT_NONE

    def upgrade(transport: Transport) -> None:
        transport.upgrade(lambda sock: context.wrap_socket(sock, server_side=False, server_hostname=server_hostname))
    return upgrade


def mutual_tls_server_upgrader(context: ssl.SSLContext) -> Callable[[Transport], None]:
    """
        Requires a client certificate; the peer identity is recorded on the transport as ``peer_identity`` and
        picked up by the server session.
    """
    context.verify_mode = ssl.CERT_REQUIRED

    def upgrade(transport: Transport) -> None:
        def wrap(sock: socket.socket) -> socket.socket:
            wrapped = context.wrap_socket(sock, server_side=True)
            cert = wrapped.getpeercert() or {}
            subject = cert.get("subject", ())
            parts = [value for rdn in subject for key, value in rdn if key == "commonName"]
            setattr(transport, "peer_identity", parts[0] if parts else None)
            return wrapped
        transport.upgrade(wrap)
    return upgrade
