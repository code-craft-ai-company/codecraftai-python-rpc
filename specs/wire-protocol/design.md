# Design Document — Wire Protocol

## Overview

The wire protocol is a small binary format with a fixed header and a per-message payload. The
header is decodable without any knowledge of the payload, so the session can correlate replies
and route requests before the dispatch worker decodes the rest. Payload encoding is delegated to
the Serialization feature so the protocol module never contains type-specific logic.

## Architecture

### Frame and Header Layout

```
+----------------+----------------------------------------------------------+
| size  (8, !Q)  | message                                                  |
+----------------+----------------------------------------------------------+

message:
+---------+-------+-------+------------------+--------------+-------------+
| version | mtype | mcode | correlation id   | payload len  | payload     |
| 2  !H   | 1  !B | 1  !B | 16 bytes         | 4  !I        | variable    |
+---------+-------+-------+------------------+--------------+-------------+
HEADER_SIZE = 24
```

The correlation id is a raw 16 byte UUID rather than its 36 character text form, which halves
the header and avoids the string-versus-bytes packing error in the current code.

### Pack and Unpack

```
Message.pack()                          Message.unpack(data)
  payload = self._pack_payload()          header = MessageHeader.unpack(data[:24])
  header  = MessageHeader(...)            check version, length
  return header.pack() + payload          cls = REGISTRY[(header.mtype, header.mcode)]
                                          return cls._unpack_payload(header, data[24:])
```

`REGISTRY` is filled by a class decorator on each message class, so adding a message is one
class definition. Payload fields are encoded with the Serialization feature's `encode` and
`decode` functions applied to a tuple of the class's fields.

### Design Decisions

1. **Fixed 24 byte header** — cheap to parse, and every routing decision the session makes needs
   only the header.
2. **Per-request correlation id** — replies are matched to requests, not to threads. One thread
   can have several calls in flight and nested callbacks work naturally.
3. **Payload length in the header** — redundant with the frame size, but it lets the receiver
   validate a frame before decoding and makes the header self-describing when logged.
4. **Registry by (type, code)** — `unpack` never grows an if-chain; unknown pairs raise
   `ProtocolError` with the values.
5. **Reply codes mirror request codes** — a reply's code says which request it answers, which
   makes wire traces readable and lets the session validate that the reply matches the waiter.
6. **One exception message class** — every failure travels the same way, with a code that
   distinguishes protocol failures from remote application exceptions.
7. **Version in every header** — the HELLO exchange picks the version, but carrying it on every
   message makes a stray frame from the wrong peer detectable.
8. **`struct` only** — no third-party framing library; the format is simple enough that
   `struct` keeps the dependency list at `codecraftai-foundations`.

## Components and Interfaces

### File Layout

```
source/packages/ccai/rpc/core/protocol/__init__.py    re-exports
source/packages/ccai/rpc/core/protocol/constants.py   versions, sizes, enums
source/packages/ccai/rpc/core/protocol/header.py      MessageHeader
source/packages/ccai/rpc/core/protocol/messages.py    Message, registry, all message classes
source/tests/test_protocol_header.py
source/tests/test_protocol_messages.py
```

The existing single `protocol.py` module becomes the `protocol` package.

### Constants

```python
PROTOCOL_VERSION = 1
MIN_SUPPORTED_VERSION = 1
HEADER_SIZE = 24
MAX_MESSAGE_SIZE = 64 * 1024 * 1024

class MessageType(IntEnum): REQUEST = 1; REPLY = 2; EXCEPTION = 3
class RequestCode(IntEnum): HELLO, PING, CLOSE, GETSERVICE, GETATTR, SETATTR, DELATTR, CALL, RELEASE, RENEW, CANCEL, PROGRESS
class ReplyCode(IntEnum):   same names and values as RequestCode
class ExceptionCode(IntEnum): REMOTE_EXCEPTION, PROTOCOL_ERROR, UNKNOWN_REFERENCE, LEASE_EXPIRED, CANCELLED, UNAUTHORIZED
```

### MessageHeader

```python
@dataclass(frozen=True)
class MessageHeader:
    version: int
    mtype: MessageType
    mcode: int
    correlation_id: uuid.UUID
    payload_length: int
    def pack(self) -> bytes
    @classmethod
    def unpack(cls, data: bytes) -> "MessageHeader"
```

### Message and Subclasses

```python
class Message:
    mtype: ClassVar[MessageType]
    mcode: ClassVar[int]
    fields: ClassVar[Tuple[str, ...]]
    correlation_id: uuid.UUID
    version: int
    def pack(self) -> bytes
    @classmethod
    def unpack(cls, data: bytes) -> "Message"

@message(MessageType.REQUEST, RequestCode.CALL)
class RequestCall(Message):
    fields = ("target_ref", "callable_name", "args", "kwargs", "deadline")
```

Request classes: `RequestHello`, `RequestPing`, `RequestClose`, `RequestGetService`,
`RequestGetAttr`, `RequestSetAttr`, `RequestDelAttr`, `RequestCall`, `RequestRelease`,
`RequestRenew`, `RequestCancel`, `RequestProgress`. Reply classes mirror them. `ExceptionMessage`
carries `code`, `type_name`, `message`, `traceback_text` and `value`.

## Testing Strategy

Header tests pack and unpack every field, reject short data, bad versions and mismatched
lengths. Message tests round-trip every class through `pack` and `unpack` with representative
payloads, check that the registry rejects unknown pairs, and check that the frame size limit is
enforced. No sockets are involved.
