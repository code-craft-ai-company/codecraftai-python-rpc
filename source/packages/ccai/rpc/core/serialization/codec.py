"""
.. module:: codec
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The tagged binary codec: a closed set of by-value types, registered user types, exceptions and
               reference placeholders. No decode path executes code.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Callable, Optional

import builtins
import datetime
import enum
import struct
import sys
import traceback
import uuid

import ccai.errors.exceptions as _ccai_exceptions

from ccai.rpc.errors import RemoteError, SerializationError
from ccai.rpc.core.proxy.wrappers import PROXY_MARKER, ByRef, ByValue, is_by_ref_type
from ccai.rpc.core.serialization.placeholder import ReferencePlaceholder
from ccai.rpc.core.serialization.tags import FORMAT_VERSION, MAX_DEPTH, Tag
from ccai.rpc.core.serialization import registry

ReferenceEncoder = Callable[[object], Optional[ReferencePlaceholder]]
ReferenceResolver = Callable[[ReferencePlaceholder], object]

# Exception types are resolved only from modules already loaded in this process; decoding never imports.
_PRELOADED_EXCEPTION_MODULES = {"builtins": builtins, "ccai.errors.exceptions": _ccai_exceptions}


def _write_varint(out: bytearray, value: int) -> None:
    if value < 0:
        raise SerializationError("varint cannot be negative")
    while True:
        byte = value & 0x7F
        value >>= 7
        if value:
            out.append(byte | 0x80)
        else:
            out.append(byte)
            return


def _read_varint(data: bytes, pos: int):
    shift = 0
    result = 0
    while True:
        if pos >= len(data):
            raise SerializationError("truncated varint")
        byte = data[pos]
        pos += 1
        result |= (byte & 0x7F) << shift
        if not (byte & 0x80):
            return result, pos
        shift += 7


def _zigzag(value: int) -> int:
    return (value << 1) if value >= 0 else ((-value << 1) - 1)


def _unzigzag(value: int) -> int:
    return (value >> 1) if not (value & 1) else -((value + 1) >> 1)


class Encoder:

    def __init__(self, ref_encoder: Optional[ReferenceEncoder] = None, known_lookup: Optional[ReferenceEncoder] = None) -> None:
        self._ref_encoder = ref_encoder
        self._known_lookup = known_lookup
        self._out = bytearray()
        return

    def encode(self, value: object) -> bytes:
        self._out = bytearray([FORMAT_VERSION])
        self._encode(value, 0, "value")
        return bytes(self._out)

    def _tag(self, tag: Tag) -> None:
        self._out.append(int(tag))
        return

    def _bytes(self, raw: bytes) -> None:
        _write_varint(self._out, len(raw))
        self._out.extend(raw)
        return

    def _str(self, text: str) -> None:
        self._bytes(text.encode("utf-8"))
        return

    def _encode(self, value: object, depth: int, path: str) -> None:
        if depth > MAX_DEPTH:
            raise SerializationError("value nesting exceeds the depth limit of {} at {}".format(MAX_DEPTH, path))
        out = self._out
        if value is None:
            self._tag(Tag.NONE)
        elif value is True:
            self._tag(Tag.TRUE)
        elif value is False:
            self._tag(Tag.FALSE)
        elif isinstance(value, int) and not isinstance(value, enum.Enum):
            self._tag(Tag.INT)
            _write_varint(out, _zigzag(value))
        elif isinstance(value, float):
            self._tag(Tag.FLOAT)
            out.extend(struct.pack("!d", value))
        elif isinstance(value, str):
            self._tag(Tag.STR)
            self._str(value)
        elif isinstance(value, (bytes, bytearray, memoryview)):
            self._tag(Tag.BYTES)
            self._bytes(bytes(value))
        elif isinstance(value, ByValue):
            self._encode(value.instance, depth, path)
        elif isinstance(value, ByRef) or is_by_ref_type(value) or getattr(type(value), PROXY_MARKER, False):
            self._reference(value.instance if isinstance(value, ByRef) else value, path)
        elif isinstance(value, enum.Enum):
            tag = registry.enum_tag_for(type(value))
            if tag is None:
                raise SerializationError("enum type '{}' is not registered (at {})".format(type(value).__name__, path))
            self._tag(Tag.ENUM)
            self._str(tag)
            self._str(value.name)
        elif isinstance(value, (list, tuple, set, frozenset)):
            tag = {list: Tag.LIST, tuple: Tag.TUPLE, set: Tag.SET, frozenset: Tag.FROZENSET}[type(value) if type(value) in (list, tuple, set, frozenset) else (list if isinstance(value, list) else tuple if isinstance(value, tuple) else set if isinstance(value, set) else frozenset)]
            self._tag(tag)
            items = list(value)
            _write_varint(out, len(items))
            for index, item in enumerate(items):
                self._encode(item, depth + 1, "{}[{}]".format(path, index))
        elif isinstance(value, dict):
            self._tag(Tag.DICT)
            _write_varint(out, len(value))
            for key, item in value.items():
                if not isinstance(key, str):
                    raise SerializationError("dict keys must be str, got {} (at {})".format(type(key).__name__, path))
                self._str(key)
                self._encode(item, depth + 1, "{}.{}".format(path, key))
        elif isinstance(value, datetime.datetime):
            if value.tzinfo is None:
                raise SerializationError("naive datetime values are not allowed on the wire (at {})".format(path))
            self._tag(Tag.DATETIME)
            self._str(value.isoformat())
        elif isinstance(value, datetime.date):
            self._tag(Tag.DATE)
            self._str(value.isoformat())
        elif isinstance(value, datetime.timedelta):
            self._tag(Tag.TIMEDELTA)
            out.extend(struct.pack("!d", value.total_seconds()))
        elif isinstance(value, uuid.UUID):
            self._tag(Tag.UUID)
            out.extend(value.bytes)
        elif isinstance(value, ReferencePlaceholder):
            self._placeholder(value)
        elif isinstance(value, BaseException):
            self._exception(value, depth, path)
        else:
            tag = registry.flattenable_tag_for(type(value))
            if tag is not None:
                self._tag(Tag.FLATTENABLE)
                self._str(tag)
                flat = value.flatten()
                self._encode(flat, depth + 1, "{}<{}>".format(path, tag))
            elif self._known_lookup is not None and self._known_lookup(value) is not None:
                # an object this session already handed out by reference travels as that reference
                self._placeholder(self._known_lookup(value))
            else:
                raise SerializationError(
                    "type '{}' cannot be sent by value; wrap it as ByRef or ByValue, or register it (at {})".format(
                        type(value).__name__, path))
        return

    def _reference(self, obj: object, path: str) -> None:
        if self._ref_encoder is None:
            raise SerializationError("a by-reference object cannot be encoded outside a session (at {})".format(path))
        placeholder = self._ref_encoder(obj)
        if placeholder is None:
            raise SerializationError("the session declined to create a reference for '{}' (at {})".format(type(obj).__name__, path))
        self._placeholder(placeholder)
        return

    def _placeholder(self, placeholder: ReferencePlaceholder) -> None:
        self._tag(Tag.REFERENCE)
        self._out.extend(placeholder.ref_id.bytes)
        self._out.extend(placeholder.session_id.bytes)
        self._str(placeholder.type_name)
        return

    def _exception(self, exc: BaseException, depth: int, path: str) -> None:
        self._tag(Tag.EXCEPTION)
        cls = type(exc)
        self._str("{}.{}".format(cls.__module__, cls.__qualname__))
        self._str(str(exc))
        try:
            probe = Encoder(self._ref_encoder)
            probe._encode(tuple(exc.args), depth + 1, path + ".args")
            args_bytes = bytes(probe._out)
        except SerializationError:
            args_bytes = b""
        self._bytes(args_bytes)
        tb = getattr(exc, "remote_traceback", None)
        if not tb:
            tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__)) if exc.__traceback__ else ""
        self._str(tb)
        return


class Decoder:

    def __init__(self, data: bytes, resolver: Optional[ReferenceResolver] = None) -> None:
        self._data = data
        self._pos = 0
        self._resolver = resolver
        return

    def decode(self) -> object:
        if len(self._data) == 0:
            raise SerializationError("empty payload")
        version = self._data[0]
        if version != FORMAT_VERSION:
            raise SerializationError("unknown serialization format version {}".format(version))
        self._pos = 1
        value = self._value(0)
        if self._pos != len(self._data):
            raise SerializationError("trailing bytes after value")
        return value

    def _take(self, count: int) -> bytes:
        if self._pos + count > len(self._data):
            raise SerializationError("truncated payload")
        chunk = self._data[self._pos:self._pos + count]
        self._pos += count
        return chunk

    def _varint(self) -> int:
        value, self._pos = _read_varint(self._data, self._pos)
        return value

    def _bytes(self) -> bytes:
        return self._take(self._varint())

    def _str(self) -> str:
        return self._bytes().decode("utf-8")

    def _value(self, depth: int) -> object:
        if depth > MAX_DEPTH:
            raise SerializationError("value nesting exceeds the depth limit of {}".format(MAX_DEPTH))
        raw_tag = self._take(1)[0]
        try:
            tag = Tag(raw_tag)
        except ValueError:
            raise SerializationError("unknown value tag {}".format(raw_tag)) from None
        if tag == Tag.NONE:
            return None
        if tag == Tag.TRUE:
            return True
        if tag == Tag.FALSE:
            return False
        if tag == Tag.INT:
            return _unzigzag(self._varint())
        if tag == Tag.FLOAT:
            return struct.unpack("!d", self._take(8))[0]
        if tag == Tag.STR:
            return self._str()
        if tag == Tag.BYTES:
            return self._bytes()
        if tag in (Tag.LIST, Tag.TUPLE, Tag.SET, Tag.FROZENSET):
            count = self._varint()
            items = [self._value(depth + 1) for _ in range(count)]
            return {Tag.LIST: list, Tag.TUPLE: tuple, Tag.SET: set, Tag.FROZENSET: frozenset}[tag](items)
        if tag == Tag.DICT:
            count = self._varint()
            result = {}
            for _ in range(count):
                key = self._str()
                result[key] = self._value(depth + 1)
            return result
        if tag == Tag.DATETIME:
            return datetime.datetime.fromisoformat(self._str())
        if tag == Tag.DATE:
            return datetime.date.fromisoformat(self._str())
        if tag == Tag.TIMEDELTA:
            return datetime.timedelta(seconds=struct.unpack("!d", self._take(8))[0])
        if tag == Tag.UUID:
            return uuid.UUID(bytes=self._take(16))
        if tag == Tag.ENUM:
            enum_tag = self._str()
            member = self._str()
            cls = registry.enum_for_tag(enum_tag)
            if cls is None:
                raise SerializationError("enum tag '{}' is not registered".format(enum_tag))
            return cls[member]
        if tag == Tag.FLATTENABLE:
            flat_tag = self._str()
            cls = registry.flattenable_for_tag(flat_tag)
            if cls is None:
                raise SerializationError("flattenable tag '{}' is not registered".format(flat_tag))
            data = self._value(depth + 1)
            return cls.unflatten(data)
        if tag == Tag.EXCEPTION:
            return self._exception()
        if tag == Tag.REFERENCE:
            ref_id = uuid.UUID(bytes=self._take(16))
            session_id = uuid.UUID(bytes=self._take(16))
            type_name = self._str()
            placeholder = ReferencePlaceholder(ref_id, session_id, type_name)
            if self._resolver is None:
                raise SerializationError("a reference placeholder cannot be decoded without a resolver")
            return self._resolver(placeholder)
        raise SerializationError("unhandled value tag {}".format(tag))

    def _exception(self) -> BaseException:
        type_name = self._str()
        message = self._str()
        args_bytes = self._bytes()
        tb_text = self._str()
        exc = _build_exception(type_name, message, args_bytes, tb_text, self._resolver)
        return exc


def _resolve_exception_type(type_name: str):
    module_name, _, qualname = type_name.rpartition(".")
    module = _PRELOADED_EXCEPTION_MODULES.get(module_name) or sys.modules.get(module_name)
    if module is None:
        return None
    obj = module
    for part in qualname.split("."):
        obj = getattr(obj, part, None)
        if obj is None:
            return None
    if isinstance(obj, type) and issubclass(obj, BaseException):
        return obj
    return None


def _build_exception(type_name: str, message: str, args_bytes: bytes, tb_text: str, resolver) -> BaseException:
    cls = _resolve_exception_type(type_name)
    exc = None
    if cls is not None:
        try:
            exc = cls(message)
        except Exception:
            exc = None
    if exc is None:
        exc = RemoteError(message, remote_type_name=type_name, remote_traceback=tb_text)
    else:
        try:
            exc.remote_traceback = tb_text
            exc.remote_type_name = type_name
        except Exception:
            # Best-effort annotation; some exception types reject new attributes, and the rebuilt
            # exception is still the correct error to surface without the remote details attached.
            pass
    return exc


def encode(value: object, ref_encoder: Optional[ReferenceEncoder] = None, known_lookup: Optional[ReferenceEncoder] = None) -> bytes:
    return Encoder(ref_encoder, known_lookup).encode(value)


def decode(data: bytes, resolver: Optional[ReferenceResolver] = None) -> object:
    return Decoder(data, resolver).decode()
