
from typing import Generic, Optional, Tuple, TypeVar, Type


import socket


from uuid import uuid4


ServiceProtocol = TypeVar("ServiceProtocol")



from mojo.rpc.core.protocol import MessageGetRoot

from mojo.rpc.core.duplexsocketio import DuplexSocketIO
from mojo.rpc.core.duplexserversession import DuplexServerSession



class MojoRpcServer(Generic[ServiceProtocol]):
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
