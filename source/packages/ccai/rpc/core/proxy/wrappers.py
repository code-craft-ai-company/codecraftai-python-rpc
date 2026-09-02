"""
.. module:: wrappers
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The ByRef and ByValue wrappers that declare, at the call site, how an object crosses the wire.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

BY_REF_MARKER = "__rpc_by_ref__"
CONCURRENT_MARKER = "__rpc_concurrent_callbacks__"
ONEWAY_MARKER = "__rpc_oneway__"
EXPOSE_PRIVATE_MARKER = "__rpc_expose_private__"
MUTABLE_SERVICE_MARKER = "__rpc_mutable_service__"
PROXY_MARKER = "__rpc_proxy__"


class RemoteMethodDescriptor:
    """
        What a get-attribute of a callable comes back as: the far side builds a bound remote method from it
        instead of holding a reference to a transient bound-method object.
    """

    __slots__ = ("name",)

    def __init__(self, name: str) -> None:
        self.name = name
        return

    def flatten(self) -> dict:
        return {"name": self.name}

    @classmethod
    def unflatten(cls, data: dict) -> "RemoteMethodDescriptor":
        return cls(data["name"])

    def __repr__(self) -> str:
        return "RemoteMethodDescriptor({!r})".format(self.name)


from ccai.rpc.core.serialization.registry import register_flattenable as _register_flattenable  # noqa: E402
_register_flattenable("ccai.rpc.method", RemoteMethodDescriptor)


class ByRef:
    """
        Marks an object as passed by reference: the owner keeps it and the far side gets a proxy.
    """

    __slots__ = ("_instance",)

    def __init__(self, instance: object) -> None:
        self._instance = instance
        return

    @property
    def instance(self) -> object:
        return self._instance

    def __repr__(self) -> str:
        return "ByRef({!r})".format(self._instance)


class ByValue:
    """
        Marks an object as passed by value: it is flattened and copied to the far side.
    """

    __slots__ = ("_instance",)

    def __init__(self, instance: object) -> None:
        self._instance = instance
        return

    @property
    def instance(self) -> object:
        return self._instance

    def __repr__(self) -> str:
        return "ByValue({!r})".format(self._instance)


def by_ref(cls: type) -> type:
    """
        Class decorator marking every instance of the class as passed by reference by default.
    """
    setattr(cls, BY_REF_MARKER, True)
    return cls


def is_by_ref_type(obj: object) -> bool:
    return bool(getattr(type(obj), BY_REF_MARKER, False))


def concurrent_callbacks(cls: type) -> type:
    """
        Class decorator: callbacks targeting instances may run concurrently rather than in order.
    """
    setattr(cls, CONCURRENT_MARKER, True)
    return cls


def oneway(method):
    """
        Method decorator: calls to this method through a proxy use fire-and-forget delivery.
    """
    setattr(method, ONEWAY_MARKER, True)
    return method


def expose_private(cls: type) -> type:
    """
        Class decorator: allows remote access to underscore-prefixed attributes.
    """
    setattr(cls, EXPOSE_PRIVATE_MARKER, True)
    return cls


def mutable_service(cls: type) -> type:
    """
        Class decorator: allows remote attribute writes and deletes on a root service object.
    """
    setattr(cls, MUTABLE_SERVICE_MARKER, True)
    return cls
