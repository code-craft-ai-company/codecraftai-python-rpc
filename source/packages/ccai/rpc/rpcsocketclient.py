"""
.. module:: rpcsocketclient
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Module that contains the RpcSocketClient entry point used to connect to a remote service.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []


from typing import Generic, Tuple, TypeVar, Type



ServiceProtocol = TypeVar("ServiceProtocol")


from ccai.rpc.core.protocol import RequestGetService


class RpcSocketClient:
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