"""
.. module:: rpcsocketserver
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Module that contains the RpcSocketServer entry point used to expose a service over a socket.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []


from typing import Generic, Optional, Tuple, TypeVar, Type


import socket


from uuid import uuid4


ServiceProtocol = TypeVar("ServiceProtocol")



from ccai.rpc.core.protocol import RequestGetService

from ccai.rpc.core.duplexsocketio import DuplexSocketIO
from ccai.rpc.core.duplexserversession import DuplexServerSession



class RpcSocketServer(Generic[ServiceProtocol]):
    """
    """

    service_protocol: Type[ServiceProtocol]

    
    def __init__(self, service_protocol: Type[ServiceProtocol], service_endpoint: Tuple[str, int], backlog: int = 1):
        
        self.service_protocol = service_protocol
        self.service_endpoint = service_endpoint
        self.backlog = backlog

        self._listen_sock = None

        self._sessions = {}

        return


    @property
    def listen_sock(self):
        return self._listen_sock
    

    def serve_forever(self):

        self._listen_sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)

        self._listen_sock.bind(self.service_endpoint)

        self._listen_sock.listen(self.backlog)


        while True:

            client_sock, client_addr = self._listen_sock.accept()

            stream = DuplexSocketIO(client_sock, client_addr)

            session_id = uuid4()

            sink = DuplexServerSession(stream)

            self._sessions[session_id] = (client_addr, sink)

            sink.start()


        return
