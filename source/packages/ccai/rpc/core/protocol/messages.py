"""
.. module:: messages
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The Message base class, the (type, code) registry and one class per request, reply and exception.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import ClassVar, Dict, Optional, Tuple, Type

import uuid

from ccai.rpc.errors import ProtocolError
from ccai.rpc.core.protocol.constants import HEADER_SIZE, PROTOCOL_VERSION, ExceptionCode, MessageType, ReplyCode, RequestCode
from ccai.rpc.core.protocol.header import MessageHeader
from ccai.rpc.core.serialization import decode, encode

REGISTRY: Dict[Tuple[MessageType, int], Type["Message"]] = {}


class Message:
    """
        Base of every message. Subclasses declare ``mtype``, ``mcode`` and ``fields``; the payload is the
        tuple of field values encoded by the serialization codec.
    """

    mtype: ClassVar[MessageType]
    mcode: ClassVar[int]
    fields: ClassVar[Tuple[str, ...]] = ()

    def __init__(self, *args, correlation_id: Optional[uuid.UUID] = None, version: int = PROTOCOL_VERSION, **kwargs) -> None:
        if len(args) > len(self.fields):
            raise TypeError("{} takes at most {} positional field values".format(type(self).__name__, len(self.fields)))
        values = dict(zip(self.fields, args))
        for name, value in kwargs.items():
            if name not in self.fields:
                raise TypeError("{} has no field '{}'".format(type(self).__name__, name))
            values[name] = value
        for name in self.fields:
            setattr(self, name, values.get(name, self.default_for(name)))
        self.correlation_id = correlation_id if correlation_id is not None else uuid.uuid4()
        self.version = version
        return

    @classmethod
    def default_for(cls, name: str):
        return None

    def field_values(self) -> tuple:
        return tuple(getattr(self, name) for name in self.fields)

    def pack(self, ref_encoder=None, known_lookup=None) -> bytes:
        payload = encode(self.field_values(), ref_encoder=ref_encoder, known_lookup=known_lookup) if self.fields else b""
        header = MessageHeader(self.version, self.mtype, int(self.mcode), self.correlation_id, len(payload))
        return header.pack() + payload

    @classmethod
    def unpack(cls, data: bytes, resolver=None) -> "Message":
        header = MessageHeader.unpack(data)
        if header.payload_length != len(data) - HEADER_SIZE:
            raise ProtocolError("header announces {} payload bytes but {} are present".format(header.payload_length, len(data) - HEADER_SIZE))
        klass = REGISTRY.get((header.mtype, header.mcode))
        if klass is None:
            raise ProtocolError("unknown message type/code {}/{}".format(header.mtype.name, header.mcode))
        payload = data[HEADER_SIZE:]
        if klass.fields:
            values = decode(payload, resolver=resolver)
            if not isinstance(values, tuple) or len(values) != len(klass.fields):
                raise ProtocolError("payload of {} does not match its {} fields".format(klass.__name__, len(klass.fields)))
            kwargs = dict(zip(klass.fields, values))
        else:
            kwargs = {}
        return klass(correlation_id=header.correlation_id, version=header.version, **kwargs)

    def __eq__(self, other) -> bool:
        return type(self) is type(other) and self.correlation_id == other.correlation_id and self.field_values() == other.field_values()

    def __hash__(self) -> int:
        return hash((type(self), self.correlation_id))

    def __repr__(self) -> str:
        pairs = ", ".join("{}={!r}".format(name, getattr(self, name)) for name in self.fields)
        return "{}({})".format(type(self).__name__, pairs)


def message(mtype: MessageType, mcode: int):
    def register(klass):
        klass.mtype = mtype
        klass.mcode = mcode
        REGISTRY[(mtype, int(mcode))] = klass
        return klass
    return register


# ---------------------------------------------------------------------------- requests

@message(MessageType.REQUEST, RequestCode.HELLO)
class RequestHello(Message):
    fields = ("version_min", "version_max", "session_id", "credential", "context")

    @classmethod
    def default_for(cls, name):
        return {"version_min": PROTOCOL_VERSION, "version_max": PROTOCOL_VERSION, "credential": b"", "context": {}}.get(name)


@message(MessageType.REQUEST, RequestCode.PING)
class RequestPing(Message):
    fields = ()


@message(MessageType.REQUEST, RequestCode.CLOSE)
class RequestClose(Message):
    fields = ()


@message(MessageType.REQUEST, RequestCode.GETSERVICE)
class RequestGetService(Message):
    fields = ()


@message(MessageType.REQUEST, RequestCode.GETATTR)
class RequestGetAttr(Message):
    fields = ("target_ref", "name", "deadline", "context")


@message(MessageType.REQUEST, RequestCode.SETATTR)
class RequestSetAttr(Message):
    fields = ("target_ref", "name", "value", "deadline", "context")


@message(MessageType.REQUEST, RequestCode.DELATTR)
class RequestDelAttr(Message):
    fields = ("target_ref", "name", "deadline", "context")


@message(MessageType.REQUEST, RequestCode.CALL)
class RequestCall(Message):
    fields = ("target_ref", "callable_name", "args", "kwargs", "deadline", "context", "notify")

    @classmethod
    def default_for(cls, name):
        return {"args": (), "kwargs": {}, "notify": False}.get(name)


@message(MessageType.REQUEST, RequestCode.RELEASE)
class RequestRelease(Message):
    fields = ("ref_id",)


@message(MessageType.REQUEST, RequestCode.RENEW)
class RequestRenew(Message):
    fields = ("ref_ids",)

    @classmethod
    def default_for(cls, name):
        return () if name == "ref_ids" else None


@message(MessageType.REQUEST, RequestCode.CANCEL)
class RequestCancel(Message):
    fields = ("target_correlation_id",)


@message(MessageType.REQUEST, RequestCode.PROGRESS)
class RequestProgress(Message):
    fields = ("target_correlation_id", "fraction", "message", "details")

    @classmethod
    def default_for(cls, name):
        return {} if name == "details" else None


# ---------------------------------------------------------------------------- replies

@message(MessageType.REPLY, ReplyCode.HELLO)
class ReplyHello(Message):
    fields = ("chosen_version", "session_id", "lease_duration", "heartbeat_interval")


@message(MessageType.REPLY, ReplyCode.PING)
class ReplyPing(Message):
    fields = ()


@message(MessageType.REPLY, ReplyCode.CLOSE)
class ReplyClose(Message):
    fields = ()


@message(MessageType.REPLY, ReplyCode.GETSERVICE)
class ReplyGetService(Message):
    fields = ("value",)


@message(MessageType.REPLY, ReplyCode.GETATTR)
class ReplyGetAttr(Message):
    fields = ("value",)


@message(MessageType.REPLY, ReplyCode.SETATTR)
class ReplySetAttr(Message):
    fields = ()


@message(MessageType.REPLY, ReplyCode.DELATTR)
class ReplyDelAttr(Message):
    fields = ()


@message(MessageType.REPLY, ReplyCode.CALL)
class ReplyCall(Message):
    fields = ("value",)


@message(MessageType.REPLY, ReplyCode.RELEASE)
class ReplyRelease(Message):
    fields = ()


@message(MessageType.REPLY, ReplyCode.RENEW)
class ReplyRenew(Message):
    fields = ("unknown",)

    @classmethod
    def default_for(cls, name):
        return () if name == "unknown" else None


@message(MessageType.REPLY, ReplyCode.CANCEL)
class ReplyCancel(Message):
    fields = ()


@message(MessageType.REPLY, ReplyCode.PROGRESS)
class ReplyProgress(Message):
    fields = ()


# ---------------------------------------------------------------------------- exceptions

@message(MessageType.EXCEPTION, 0)
class ExceptionMessage(Message):
    fields = ("code", "type_name", "message", "traceback_text", "value")

    @classmethod
    def default_for(cls, name):
        return {"code": int(ExceptionCode.REMOTE_EXCEPTION), "type_name": "", "message": "", "traceback_text": ""}.get(name)

    @classmethod
    def from_exception(cls, exc: BaseException, code: ExceptionCode = ExceptionCode.REMOTE_EXCEPTION,
                       correlation_id: Optional[uuid.UUID] = None) -> "ExceptionMessage":
        import traceback as _tb
        klass = type(exc)
        tb = getattr(exc, "remote_traceback", None) or ("".join(_tb.format_exception(klass, exc, exc.__traceback__)) if exc.__traceback__ else "")
        return cls(code=int(code), type_name="{}.{}".format(klass.__module__, klass.__qualname__), message=str(exc),
                   traceback_text=tb, value=exc, correlation_id=correlation_id)


REPLY_FOR_REQUEST: Dict[int, Type[Message]] = {
    int(RequestCode[name]): REGISTRY[(MessageType.REPLY, int(ReplyCode[name]))] for name in RequestCode.__members__
}
