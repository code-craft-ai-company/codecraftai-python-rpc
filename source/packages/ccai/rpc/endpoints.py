"""
.. module:: endpoints
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Endpoint types and the provider seam through which discovery packages supply addresses.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Callable, Protocol, Tuple, Union, runtime_checkable

from dataclasses import dataclass

Endpoint = Tuple[str, int]
EndpointProvider = Callable[[], Endpoint]


@runtime_checkable
class IServiceEndpoint(Protocol):
    host: str
    port: int
    service_name: str


@dataclass(frozen=True)
class ServiceEndpoint:
    host: str
    port: int
    service_name: str

    def as_tuple(self) -> Endpoint:
        return (self.host, self.port)


def resolve_endpoint(endpoint: Union[Endpoint, EndpointProvider, IServiceEndpoint]) -> Endpoint:
    if callable(endpoint):
        endpoint = endpoint()
    if isinstance(endpoint, IServiceEndpoint) and not isinstance(endpoint, tuple):
        return (endpoint.host, endpoint.port)
    host, port = endpoint
    return (host, int(port))
