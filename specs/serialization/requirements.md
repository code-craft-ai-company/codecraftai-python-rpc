# Requirements Document — Serialization

## Introduction

The Serialization feature defines how values are encoded into message payloads and decoded on
the far side. It establishes a closed set of types that pass by value, the `Flattenable` protocol
through which user types opt in, the encoding of exceptions, and the encoding of reference
placeholders that stand in for `ByRef` objects. The feature deliberately excludes pickle from the
default path, because an RPC endpoint that unpickles arbitrary input executes arbitrary code. It
is consumed by the Wire Protocol for payloads and by Object Proxies for values crossing the wire.

## Glossary

- **By-value type**: A type whose instances are copied to the far side. Membership in the set is
  explicit.
- **Flattenable**: The protocol a user type implements to be passed by value. `flatten` returns
  a by-value structure; `unflatten` rebuilds the instance.
- **Reference placeholder**: An encoded stand-in for a `ByRef` object carrying the reference id,
  the owning session id and the object's type name.
- **Type registry**: The table mapping a type tag to the encoder and decoder for that type.
- **Codec**: The pair of `encode` and `decode` functions that turn a Python value into bytes
  and back.
- **SerializationError**: The `codecraftai-errors` exception raised when a value cannot be encoded
  or decoded.

## Requirements

### Requirement 1: By-Value Type Set

**User Story:** As a service author, I want a documented set of types that cross the wire by
value, so that I know without experimenting what a method can accept and return.

#### Acceptance Criteria

1. THE codec SHALL encode and decode `None`, `bool`, `int`, `float`, `str`, `bytes`, `list`,
   `tuple`, `dict` with string keys, `set`, `frozenset`, `datetime.datetime`, `datetime.date`,
   `datetime.timedelta`, `uuid.UUID` and `enum.Enum` members of registered enum types.
2. THE codec SHALL preserve the distinction between `list` and `tuple`, between `set` and
   `frozenset`, and between `int` and `bool`.
3. THE codec SHALL encode `datetime` values with their timezone when present and SHALL reject
   naive `datetime` values with `SerializationError` unless a naive policy is registered.
4. WHEN a value's type is not in the set, is not `Flattenable` and is not wrapped as `ByRef`,
   THE codec SHALL raise `SerializationError` naming the type and, when nested, the path to it.
5. THE codec SHALL support nesting of container types to a documented depth limit and SHALL
   raise `SerializationError` beyond it.

### Requirement 2: Flattenable Protocol

**User Story:** As a service author, I want to pass my own data classes by value, so that
request and reply payloads can be domain objects rather than dictionaries.

#### Acceptance Criteria

1. THE Flattenable protocol SHALL define `flatten(self) -> dict` returning a dictionary whose
   values are by-value types or Flattenable instances.
2. THE Flattenable protocol SHALL define a class method `unflatten(cls, data: dict)` returning an
   instance.
3. THE codec SHALL provide a `register_flattenable` function that associates a type tag with a
   Flattenable class, and SHALL raise `SerializationError` on decode for an unregistered tag.
4. THE codec SHALL encode a Flattenable instance as its type tag plus the flattened dictionary.
5. WHEN `flatten` is not implemented, THE Flattenable base SHALL raise `AbstractMethodError`.
6. THE codec SHALL support `dataclasses.dataclass` types whose fields are by-value types through
   a `register_dataclass` helper that generates `flatten` and `unflatten`.

### Requirement 3: Exception Encoding

**User Story:** As a caller, I want a remote failure to arrive as the same exception type with
the remote traceback attached, so that the failure is diagnosable from my side.

#### Acceptance Criteria

1. THE codec SHALL encode an exception as its fully qualified type name, its `str` message, its
   `args` when they are by-value types, and its formatted traceback text.
2. WHEN decoding an exception whose type is importable and is a subclass of `Exception`, THE
   codec SHALL instantiate that type with the message.
3. WHEN decoding an exception whose type is not importable, THE codec SHALL instantiate
   `RemoteError` from `ccai.rpc` carrying the original type name.
4. THE decoded exception SHALL carry the remote traceback text as a `remote_traceback` attribute
   and SHALL include it in `__str__`.
5. THE codec SHALL NOT import arbitrary modules to resolve an exception type; only modules
   already imported in the process and the `ccai.errors.exceptions` module are consulted.

### Requirement 4: Reference Placeholders

**User Story:** As a proxy author, I want a `ByRef` object to travel as an identifier, so that
the far side can build a proxy without the object ever being copied.

#### Acceptance Criteria

1. THE codec SHALL encode a `ByRef` wrapper as a placeholder carrying the reference id, the
   owning session id and the wrapped object's type name.
2. THE codec SHALL accept a resolver at decode time, and WHEN a placeholder is decoded THE codec
   SHALL call the resolver with the placeholder to obtain the proxy.
3. WHEN a placeholder is decoded without a resolver, THE codec SHALL raise `SerializationError`.
4. THE codec SHALL encode a `ByValue` wrapper as the wrapped value with the wrapper removed.

### Requirement 5: Codec Interface and Safety

**User Story:** As a maintainer, I want one encode and one decode function with a stable
format, so that every payload in the protocol is produced the same way and no path unpickles
input.

#### Acceptance Criteria

1. THE codec SHALL provide `encode(value) -> bytes` and `decode(data, resolver=None) -> object`.
2. THE codec SHALL use a self-describing tagged binary format where each value begins with a one
   byte type tag.
3. THE codec SHALL NOT use `pickle`, `marshal` or `eval` on any decode path.
4. THE codec SHALL include a one byte format version at the start of every payload and SHALL
   raise `SerializationError` for an unknown version.
5. FOR every value in the by-value set, `decode(encode(value))` SHALL equal `value`.
