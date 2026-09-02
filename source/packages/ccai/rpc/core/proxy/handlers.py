"""
.. module:: handlers
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Owner-side handlers for get-service, attribute access and calls, with the attribute policy.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from ccai.rpc.errors import UnknownReferenceError
from ccai.rpc.core.protocol.constants import RequestCode
from ccai.rpc.core.protocol.messages import ReplyCall, ReplyDelAttr, ReplyGetAttr, ReplyGetService, ReplySetAttr
from ccai.rpc.core.proxy.remoteproxy import FORWARDED_DUNDERS
from ccai.rpc.core.proxy.table import ROOT_REFERENCE_ID
from ccai.rpc.core.proxy.wrappers import ByRef, EXPOSE_PRIVATE_MARKER, MUTABLE_SERVICE_MARKER, RemoteMethodDescriptor, is_by_ref_type

import inspect
from ccai.rpc.core.serialization.registry import flattenable_tag_for

_BY_VALUE_TYPES = (type(None), bool, int, float, str, bytes, list, tuple, dict, set, frozenset)


def _check_attribute(obj, name: str, write: bool, ref_id) -> None:
    if name.startswith("_") and name not in FORWARDED_DUNDERS and not getattr(type(obj), EXPOSE_PRIVATE_MARKER, False):
        raise AttributeError("remote access to private attribute '{}' of {} is refused".format(name, type(obj).__name__))
    if write and ref_id == ROOT_REFERENCE_ID and not getattr(type(obj), MUTABLE_SERVICE_MARKER, False):
        raise AttributeError("remote writes to the root service object are refused; decorate the service with @mutable_service to allow them")
    return


def _outbound(value):
    """
        Values that cannot go by value are handed out by reference, so a returned object becomes a proxy.
    """
    import datetime, enum, uuid
    if isinstance(value, _BY_VALUE_TYPES + (datetime.datetime, datetime.date, datetime.timedelta, uuid.UUID, enum.Enum, BaseException)):
        return value
    if flattenable_tag_for(type(value)) is not None or isinstance(value, ByRef) or is_by_ref_type(value):
        return value
    from ccai.rpc.core.proxy.remoteproxy import RemoteProxy
    if isinstance(value, RemoteProxy):
        return value
    return ByRef(value)


def handle_get_service(session, message, context):
    if not session.table.has_root():
        raise UnknownReferenceError("this session serves no root object")
    return ReplyGetService(value=ByRef(session.table.resolve(ROOT_REFERENCE_ID)))


def handle_get_attr(session, message, context):
    obj = session.table.resolve(message.target_ref, session.peer_session_id)
    _check_attribute(obj, message.name, False, message.target_ref)
    value = getattr(obj, message.name)
    if inspect.ismethod(value) or inspect.isbuiltin(value) or (inspect.isfunction(value) and not hasattr(value, "flatten")):
        return ReplyGetAttr(value=RemoteMethodDescriptor(message.name))
    return ReplyGetAttr(value=_outbound(value))


def handle_set_attr(session, message, context):
    obj = session.table.resolve(message.target_ref, session.peer_session_id)
    _check_attribute(obj, message.name, True, message.target_ref)
    setattr(obj, message.name, message.value)
    return ReplySetAttr()


def handle_del_attr(session, message, context):
    obj = session.table.resolve(message.target_ref, session.peer_session_id)
    _check_attribute(obj, message.name, True, message.target_ref)
    delattr(obj, message.name)
    return ReplyDelAttr()


def handle_call(session, message, context):
    obj = session.table.resolve(message.target_ref, session.peer_session_id)
    name = message.callable_name
    args = tuple(message.args or ())
    kwargs = dict(message.kwargs or {})
    if name == "__call__":
        result = obj(*args, **kwargs)
    elif name == "__rpc_iter__":
        result = list(iter(obj))
    else:
        _check_attribute(obj, name, False, message.target_ref)
        result = getattr(obj, name)(*args, **kwargs)
    if message.notify:
        return None
    return ReplyCall(value=_outbound(result))


def install(session) -> None:
    session.register_handler(RequestCode.GETSERVICE, handle_get_service)
    session.register_handler(RequestCode.GETATTR, handle_get_attr)
    session.register_handler(RequestCode.SETATTR, handle_set_attr)
    session.register_handler(RequestCode.DELATTR, handle_del_attr)
    session.register_handler(RequestCode.CALL, handle_call)
    return
