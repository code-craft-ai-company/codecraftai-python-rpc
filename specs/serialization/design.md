# Design Document — Serialization

## Overview

Serialization turns Python values into payload bytes and back using a tagged binary format with
a closed type set. The format is deliberately simple: one byte of type tag per value, lengths as
big-endian integers, containers as a count followed by their elements. User types opt in through
`Flattenable`; references travel as placeholders; exceptions travel as type name, message and
traceback text. There is no pickle anywhere.

## Architecture

### Encoding Model

```
payload := format_version(1) value
value   := tag(1) body
tag     := NONE | TRUE | FALSE | INT | FLOAT | STR | BYTES | LIST | TUPLE | DICT | SET | FROZENSET
         | DATETIME | DATE | TIMEDELTA | UUID | ENUM | FLATTENABLE | EXCEPTION | REFERENCE
```

- Scalars: `INT` is a zigzag varint; `FLOAT` is `!d`; `STR` and `BYTES` are a varint length and
  the bytes.
- Containers: a varint count followed by elements; `DICT` alternates key and value with keys
  required to be `STR`.
- `DATETIME`: ISO 8601 text with offset; `DATE`: ISO text; `TIMEDELTA`: `!d` seconds.
- `ENUM`: registered type tag string plus the member name.
- `FLATTENABLE`: registered type tag string plus a `DICT`.
- `EXCEPTION`: type name, message, `args` as a `TUPLE` or `NONE`, traceback text.
- `REFERENCE`: reference id `UUID`, owning session id `UUID`, type name `STR`.

### Decode with Resolver

```
decode(data, resolver)
  version check
  _decode_value(stream)
    REFERENCE -> resolver(ReferencePlaceholder(...)) or SerializationError
    FLATTENABLE -> registry[tag].unflatten(dict)
    EXCEPTION -> _build_exception(...)
```

The resolver is supplied by the session, which knows how to build a proxy for a reference from
the far side and how to look up a local object when a reference to one of its own objects comes
back.

### Design Decisions

1. **Own format instead of JSON or msgpack** — JSON loses `bytes`, `tuple` and `datetime`;
   msgpack adds a dependency. The type set is small and a tagged format is under 300 lines.
2. **Closed set, loud failure** — an unregistered type raises at encode time with the path to
   the offending value, for example `kwargs.options.listener`, which is the moment the author can
   fix it.
3. **No pickle** — a deserialization path that executes code is unacceptable for a service that
   accepts connections from lab hosts. `RemoteError` handles unknown exception types rather than
   importing them.
4. **Exception type resolution is restricted** — only `ccai.errors.exceptions` and already
   imported modules are consulted, so decoding cannot trigger imports.
5. **Naive datetimes rejected by default** — distributed automation across hosts in different
   timezones is exactly where naive datetimes cause silent errors.
6. **`ByValue` is transparent** — it exists to make intent visible at the call site; the codec
   strips it.
7. **Dataclass helper** — most service payloads are simple records; generating `flatten` and
   `unflatten` for dataclasses removes boilerplate without opening the type set.

## Components and Interfaces

### File Layout

```
source/packages/ccai/rpc/core/serialization/__init__.py   encode, decode, register_*
source/packages/ccai/rpc/core/serialization/tags.py       Tag enum, FORMAT_VERSION
source/packages/ccai/rpc/core/serialization/codec.py      Encoder, Decoder
source/packages/ccai/rpc/core/serialization/registry.py   type registry
source/packages/ccai/rpc/core/serialization/placeholder.py ReferencePlaceholder
source/packages/ccai/rpc/core/flattenable.py              Flattenable (existing, extended)
source/packages/ccai/rpc/errors.py                        RemoteError, SerializationError re-export
source/tests/test_serialization_scalars.py
source/tests/test_serialization_containers.py
source/tests/test_serialization_flattenable.py
source/tests/test_serialization_exceptions.py
source/tests/test_serialization_references.py
```

### Public Functions

```python
def encode(value: object) -> bytes
def decode(data: bytes, resolver: Optional[Callable[[ReferencePlaceholder], object]] = None) -> object
def register_flattenable(tag: str, cls: Type[Flattenable]) -> None
def register_enum(tag: str, cls: Type[enum.Enum]) -> None
def register_dataclass(tag: str, cls: type) -> None
```

### Flattenable

```python
class Flattenable(Protocol):
    def flatten(self) -> dict: ...
    @classmethod
    def unflatten(cls, data: dict) -> "Flattenable": ...
```

### ReferencePlaceholder

```python
@dataclass(frozen=True)
class ReferencePlaceholder:
    ref_id: uuid.UUID
    session_id: uuid.UUID
    type_name: str
```

### RemoteError

```python
class RemoteError(RuntimeError):
    remote_type_name: str
    remote_traceback: str
```

Every decoded exception, including known types, gets `remote_traceback` set and appended to
`__str__` output.

## Testing Strategy

Scalar and container tests round-trip every type in the set, including the list versus tuple
and int versus bool distinctions, nested structures and the depth limit. Flattenable tests cover
registration, round trip, unregistered tags and the dataclass helper. Exception tests cover a
known `ccai.errors` type, a built-in type, an unknown type becoming `RemoteError`, and that the
traceback text survives. Reference tests cover placeholder encoding, resolver invocation and the
no-resolver error. A property-style test encodes random nested values and checks equality.
