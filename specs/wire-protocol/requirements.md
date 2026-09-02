# Requirements Document — Wire Protocol

## Introduction

The Wire Protocol feature defines how `codecraftai-python-rpc` messages are laid out on the
socket. It covers the frame that carries every message, the fixed header every message begins
with, the vocabulary of message types and codes, the message classes that represent each
operation in Python, and the symmetric `pack` and `unpack` operations both ends use. The feature
depends on Serialization for encoding message payloads and is consumed by Sessions, which route
on the unpacked messages. The protocol is versioned from the first release so that the format can
evolve without silently misreading frames.

## Glossary

- **Frame**: The unit of transmission on the socket: an 8 byte big-endian unsigned size followed
  by exactly that many bytes of message.
- **Header**: The fixed-size prefix of every message: protocol version, message type, message
  code and correlation id.
- **Message type**: One of REQUEST, REPLY or EXCEPTION.
- **Message code**: Identifies the operation within a type, such as PING, CALL or GETATTR.
- **Correlation id**: A 16 byte UUID chosen by the sender of a request and echoed in its reply or
  exception, used to match replies to waiting callers.
- **Payload**: The bytes after the header, whose layout is defined per message code and encoded
  by the Serialization feature.
- **Message class**: A Python class representing one message code, with typed fields, a `pack`
  method and an `unpack` class method.
- **ProtocolError**: The `codecraftai-errors` exception raised for malformed or unexpected
  messages.

## Requirements

### Requirement 1: Framing

**User Story:** As a transport author, I want every message to be delimited by a size prefix,
so that the transport can read complete messages without understanding their contents.

#### Acceptance Criteria

1. THE protocol SHALL precede every message with an 8 byte big-endian unsigned size that counts
   the message bytes and excludes the size field itself.
2. THE protocol SHALL define a maximum message size constant, and WHEN a frame announces a size
   above it, THE receiver SHALL raise `ProtocolError` and close the connection.
3. THE protocol SHALL define a zero-length message as invalid.

### Requirement 2: Message Header

**User Story:** As a session author, I want a fixed header on every message, so that I can route
a message by type and code and correlate a reply before decoding any payload.

#### Acceptance Criteria

1. THE header SHALL consist of, in order, a 2 byte protocol version, a 1 byte message type, a 1
   byte message code, a 16 byte correlation id and a 4 byte payload length, all big-endian.
2. THE protocol SHALL define `HEADER_SIZE` as the header length and SHALL raise `ProtocolError`
   when a message is shorter than `HEADER_SIZE`.
3. WHEN the payload length in the header does not equal the message length minus `HEADER_SIZE`,
   THE receiver SHALL raise `ProtocolError`.
4. THE protocol SHALL provide a `MessageHeader` class with `pack` and `unpack` that round-trips
   every field.

### Requirement 3: Message Types and Codes

**User Story:** As a protocol implementer, I want a closed vocabulary of message types and
codes, so that both ends agree on every operation and unknown values are rejected.

#### Acceptance Criteria

1. THE protocol SHALL define message types REQUEST, REPLY and EXCEPTION as an `IntEnum`.
2. THE protocol SHALL define request codes HELLO, PING, CLOSE, GETSERVICE, GETATTR, SETATTR,
   DELATTR, CALL, RELEASE, RENEW, CANCEL and PROGRESS as an `IntEnum`.
3. THE protocol SHALL define reply codes that correspond one to one with the request codes.
4. THE protocol SHALL define exception codes REMOTE_EXCEPTION, PROTOCOL_ERROR, UNKNOWN_REFERENCE,
   LEASE_EXPIRED, CANCELLED and UNAUTHORIZED.
5. WHEN an unknown type or code is unpacked, THE protocol SHALL raise `ProtocolError` naming the
   value.

### Requirement 4: Message Classes

**User Story:** As a session author, I want a typed class per message, so that dispatch code
reads fields by name and never by byte offset.

#### Acceptance Criteria

1. THE protocol SHALL provide one class per request code, one per reply code and one exception
   class, each deriving from a `Message` base class.
2. THE Message base class SHALL expose `mtype`, `mcode`, `correlation_id` and `version` and SHALL
   provide `pack` returning the complete message bytes including the header.
3. THE Message base class SHALL provide an `unpack` class method that reads the header, selects
   the message class by type and code, decodes the payload and returns the typed instance.
4. THE RequestCall class SHALL carry a target reference id, a callable name, positional
   arguments, keyword arguments and an optional deadline in seconds.
5. THE RequestGetAttr, RequestSetAttr and RequestDelAttr classes SHALL carry a target reference
   id and an attribute name, and RequestSetAttr SHALL also carry a value.
6. THE ReplyCall, ReplyGetAttr and ReplyGetService classes SHALL carry a result value encoded by
   the Serialization feature.
7. THE ExceptionMessage class SHALL carry an exception code, the exception type name, the
   message text, the remote traceback text and an optional encoded exception value.
8. THE RequestHello class SHALL carry the sender's supported protocol version range, session id
   and optional credential bytes, and ReplyHello SHALL carry the chosen version, the server
   session id and the server's lease duration.
9. THE RequestRenew class SHALL carry a list of reference ids, and RequestRelease SHALL carry one
   reference id.
10. FOR every message class, `unpack(cls_instance.pack())` SHALL produce an equal instance.

### Requirement 5: Versioning

**User Story:** As a maintainer, I want the protocol versioned, so that a newer client and an
older server fail clearly at connect time instead of misreading frames mid-run.

#### Acceptance Criteria

1. THE protocol SHALL define `PROTOCOL_VERSION` and `MIN_SUPPORTED_VERSION` constants.
2. WHEN a message header carries a version outside the supported range, THE receiver SHALL raise
   `ProtocolError` naming both versions.
3. THE HELLO exchange SHALL select the highest version supported by both ends, and every
   subsequent message on the session SHALL carry that version.
