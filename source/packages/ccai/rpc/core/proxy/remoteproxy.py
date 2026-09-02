"""
.. module:: remoteproxy
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: RemoteProxy, the holder-side stand-in that forwards attribute access and calls to the owner.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Optional

import uuid

from ccai.rpc.errors import SessionClosedError
from ccai.rpc.core.protocol.messages import RequestCall, RequestDelAttr, RequestGetAttr, RequestSetAttr
from ccai.rpc.core.proxy.wrappers import ONEWAY_MARKER, RemoteMethodDescriptor

_OWN = ("_session", "_ref_id", "_owner_session_id", "_type_name", "_protocol", "_aspects", "_closed", "_is_view", "_expired", "_base", "_methods")
FORWARDED_DUNDERS = ("__len__", "__contains__", "__getitem__", "__setitem__", "__delitem__", "__enter__", "__exit__", "__call__", "__rpc_iter__")


class _RemoteMethod:
    """
        A bound remote callable. Calling it is exactly one round trip.
    """

    __slots__ = ("_proxy", "_name")

    def __init__(self, proxy: "RemoteProxy", name: str) -> None:
        self._proxy = proxy
        self._name = name
        return

    def __call__(self, *args, **kwargs):
        if self._proxy._protocol is not None:
            attr = getattr(self._proxy._protocol, self._name, None)
            if attr is not None and getattr(attr, ONEWAY_MARKER, False):
                self._proxy.rpc_notify(self._name, *args, **kwargs)
                return None
        return self._proxy._call(self._name, args, kwargs)

    def rpc_notify(self, *args, **kwargs) -> None:
        self._proxy.rpc_notify(self._name, *args, **kwargs)
        return

    def rpc_call_async(self, *args, **kwargs):
        return self._proxy.rpc_call_async(self._name, *args, **kwargs)

    def __repr__(self) -> str:
        return "<remote method {}.{} via {}>".format(self._proxy._type_name, self._name, self._proxy._ref_id)


class RemoteProxy:
    """
        Forwards attribute get, set, delete and calls to the owning session as protocol requests. Its own
        state is reachable through ``rpc_``-prefixed names so it cannot collide with the target's attributes.
    """

    __slots__ = _OWN + ("__weakref__",)
    __rpc_proxy__ = True

    def __init__(self, session, ref_id: uuid.UUID, owner_session_id: uuid.UUID, type_name: str,
                 protocol: Optional[type] = None, aspects=None, is_view: bool = False, base: Optional["RemoteProxy"] = None) -> None:
        object.__setattr__(self, "_session", session)
        object.__setattr__(self, "_ref_id", ref_id)
        object.__setattr__(self, "_owner_session_id", owner_session_id)
        object.__setattr__(self, "_type_name", type_name)
        object.__setattr__(self, "_protocol", protocol)
        object.__setattr__(self, "_aspects", aspects)
        object.__setattr__(self, "_closed", False)
        object.__setattr__(self, "_is_view", is_view)
        object.__setattr__(self, "_expired", False)
        object.__setattr__(self, "_base", base)          # a view keeps its base alive so the reference is not released under it
        object.__setattr__(self, "_methods", {})
        return

    # ------------------------------------------------------------------ own surface
    @property
    def rpc_reference_id(self) -> uuid.UUID:
        return self._ref_id

    @property
    def rpc_remote_type_name(self) -> str:
        return self._type_name

    @property
    def rpc_session(self):
        return self._session

    @property
    def rpc_owner_session_id(self) -> uuid.UUID:
        return self._owner_session_id

    @property
    def rpc_closed(self) -> bool:
        return self._closed

    @property
    def rpc_expired(self) -> bool:
        return self._expired

    def rpc_mark_closed(self) -> None:
        object.__setattr__(self, "_closed", True)
        return

    def rpc_mark_expired(self) -> None:
        object.__setattr__(self, "_expired", True)
        return

    def rpc_release(self) -> None:
        """
            Releases the reference on the owner now rather than waiting for garbage collection.
        """
        if not self._closed and not self._is_view:
            self._session.release_reference(self._ref_id)
            object.__setattr__(self, "_closed", True)
        return

    def rpc_with_aspects(self, aspects) -> "RemoteProxy":
        return RemoteProxy(self._session, self._ref_id, self._owner_session_id, self._type_name, self._protocol, aspects, is_view=True, base=self._base or self)

    def rpc_with_protocol(self, protocol: Optional[type]) -> "RemoteProxy":
        return RemoteProxy(self._session, self._ref_id, self._owner_session_id, self._type_name, protocol, self._aspects, is_view=True, base=self._base or self)

    def rpc_notify(self, name: str, *args, **kwargs) -> None:
        self._check_usable()
        self._session.send_notification(RequestCall(target_ref=self._ref_id, callable_name=name, args=tuple(args), kwargs=dict(kwargs),
                                                    deadline=None, context=self._session.request_context(), notify=True))
        return

    def rpc_call_async(self, name: str, *args, **kwargs):
        self._check_usable()
        aspects = self._session.resolve_aspects(self._aspects)
        message = RequestCall(target_ref=self._ref_id, callable_name=name, args=tuple(args), kwargs=dict(kwargs),
                              deadline=aspects.completion_timeout, context=self._session.request_context())
        return self._session.send_request_async(message, timeout=aspects.completion_timeout, unwrap=True)

    # ------------------------------------------------------------------ forwarding
    def _check_usable(self) -> None:
        if self._base is not None and (self._base._closed or self._base._expired):
            object.__setattr__(self, "_closed", self._base._closed)
            object.__setattr__(self, "_expired", self._base._expired)
        if self._closed or not self._session.is_running:
            raise SessionClosedError("proxy for {} ({}) is no longer usable: the session is closed".format(self._type_name, self._ref_id))
        if self._expired:
            from ccai.rpc.errors import LeaseExpiredError
            raise LeaseExpiredError("proxy for {} ({}) expired: the owner no longer holds the reference".format(self._type_name, self._ref_id))
        return

    def _request(self, message):
        self._check_usable()
        aspects = self._session.resolve_aspects(self._aspects)
        message.deadline = aspects.completion_timeout
        message.context = self._session.request_context()
        return self._session.send_request(message, timeout=aspects.completion_timeout)

    def _call(self, name: str, args: tuple, kwargs: dict):
        reply = self._request(RequestCall(target_ref=self._ref_id, callable_name=name, args=tuple(args), kwargs=dict(kwargs)))
        return reply.value

    def _protocol_declares(self, name: str) -> bool:
        if self._protocol is None:
            return False
        if hasattr(self._protocol, name):
            return True
        for klass in getattr(self._protocol, "__mro__", ()):
            if name in getattr(klass, "__annotations__", {}):
                return True
        return False

    def __getattr__(self, name: str):
        if name.startswith("rpc_") or name in _OWN:
            raise AttributeError(name)
        if name.startswith("__") and name.endswith("__"):
            raise AttributeError(name)
        cached = self._methods.get(name)
        if cached is not None:
            return cached
        if self._protocol is not None:
            if not self._protocol_declares(name):
                raise AttributeError("'{}' is not declared by the service protocol {}".format(name, self._protocol.__name__))
            if callable(getattr(self._protocol, name, None)):
                method = _RemoteMethod(self, name)
                self._methods[name] = method
                return method
        reply = self._request(RequestGetAttr(target_ref=self._ref_id, name=name))
        value = reply.value
        if isinstance(value, RemoteMethodDescriptor):
            method = _RemoteMethod(self, value.name)
            self._methods[name] = method
            return method
        if isinstance(value, RemoteProxy) and self._aspects is not None:
            value = value.rpc_with_aspects(self._aspects)
        return value

    def __setattr__(self, name: str, value) -> None:
        if name in _OWN:
            object.__setattr__(self, name, value)
            return
        self._request(RequestSetAttr(target_ref=self._ref_id, name=name, value=value))
        return

    def __delattr__(self, name: str) -> None:
        self._request(RequestDelAttr(target_ref=self._ref_id, name=name))
        return

    def __call__(self, *args, **kwargs):
        return self._call("__call__", args, kwargs)

    def __len__(self) -> int:
        return self._call("__len__", (), {})

    def __iter__(self):
        return iter(self._call("__rpc_iter__", (), {}))

    def __contains__(self, item) -> bool:
        return self._call("__contains__", (item,), {})

    def __getitem__(self, key):
        return self._call("__getitem__", (key,), {})

    def __setitem__(self, key, value) -> None:
        self._call("__setitem__", (key, value), {})
        return

    def __delitem__(self, key) -> None:
        self._call("__delitem__", (key,), {})
        return

    def __enter__(self):
        self._call("__enter__", (), {})
        return self

    def __exit__(self, exc_type, exc, tb):
        return self._call("__exit__", (None, None, None), {})

    def __bool__(self) -> bool:
        return True

    def __eq__(self, other) -> bool:
        return isinstance(other, RemoteProxy) and other._ref_id == self._ref_id and other._owner_session_id == self._owner_session_id

    def __hash__(self) -> int:
        return hash((self._ref_id, self._owner_session_id))

    def __repr__(self) -> str:
        return "<RemoteProxy {} ref={} owner={}{}>".format(self._type_name, self._ref_id, self._owner_session_id,
                                                          " closed" if self._closed else "")
