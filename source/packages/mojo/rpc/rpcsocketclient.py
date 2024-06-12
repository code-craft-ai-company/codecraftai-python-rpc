

from typing import Generic, Tuple, TypeVar, Type



ServiceProtocol = TypeVar("ServiceProtocol")


from mojo.rpc.core.protocol import RequestGetService


class MojoRpcClient:
    """
    """


    service_protocol: Type[ServiceProtocol]


    def __init__(self, service_protocol: Type[ServiceProtocol], service_endpoint: Tuple[str, int]):

        self.service_protocol = service_protocol
        self.service_endpoint = service_endpoint

        return


    def connect(self):



        return


    def get_service(self) -> ServiceProtocol:
        """
            Get the remote services object.
        """

        return