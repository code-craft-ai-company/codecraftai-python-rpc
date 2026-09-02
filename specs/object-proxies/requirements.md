# Requirements Document — Object Proxies

## Introduction

The Object Proxies feature is how objects are shared between processes without being copied.
A `ByRef` wrapper declares that an object stays with its owner and the far side receives a
proxy; a `ByValue` wrapper declares that a copy is sent. The feature covers the wrappers, the
proxy class that forwards operations as protocol requests, the reference table on the owning
side, release of references when a proxy is collected, and the typed service proxy that
`get_service` returns. It depends on Sessions and Serialization and is consumed by Callback
Dispatch, Leases and the Entry Points.

## Glossary

- **ByRef**: A wrapper that marks an object as passed by reference. The owner keeps the object;
  the far side gets a proxy.
- **ByValue**: A wrapper that marks an object as passed by value. It is stripped at encode time.
- **Reference id**: A UUID assigned when an object is first registered in the owner's reference
  table.
- **Reference table**: The owner-side mapping from reference id to object, holder count and
  lease state.
- **RemoteProxy**: The far-side stand-in that forwards attribute access, assignment, deletion
  and calls to the owner as requests.
- **Service proxy**: The `RemoteProxy` for the root service object, returned by `get_service`.
- **UnknownReferenceError**: The `ccai.errors` exception raised when a request names a
  reference id the owner does not hold.

## Requirements

### Requirement 1: Passing Declarations

**User Story:** As a service author, I want to say at the call site whether an argument is
proxied or copied, so that a reader of my code knows what crosses the wire.

#### Acceptance Criteria

1. THE ByRef wrapper SHALL accept an object and expose it as a read-only `instance` property.
2. THE ByValue wrapper SHALL accept an object and expose it as a read-only `instance` property.
3. WHEN a non-by-value, non-Flattenable object is passed unwrapped as an argument or return
   value, THE proxy layer SHALL raise `SerializationError` before any bytes are sent.
4. THE ByRef wrapper SHALL be idempotent with respect to the reference table: wrapping the same
   object twice within one session SHALL yield the same reference id.
5. THE package SHALL provide a `by_ref` class decorator that marks every instance of a class as
   passed by reference by default, so that listener and handle classes need no wrapping at call
   sites.

### Requirement 2: Reference Table

**User Story:** As a session author, I want the owner to track every object it has handed out,
so that requests can be resolved to objects and objects can be released.

#### Acceptance Criteria

1. THE ReferenceTable SHALL provide `register(obj) -> ref_id` that returns the existing id for an
   already registered object and assigns a new UUID otherwise.
2. THE ReferenceTable SHALL provide `resolve(ref_id) -> object` and SHALL raise
   `UnknownReferenceError` naming the id for an unknown or released reference.
3. THE ReferenceTable SHALL count holders per reference: each encode of the reference to the peer
   increments the count, and each RequestRelease decrements it.
4. WHEN a reference's holder count reaches zero, THE ReferenceTable SHALL remove the entry.
5. THE ReferenceTable SHALL provide `release_all` used at session teardown.
6. THE ReferenceTable SHALL reserve a fixed reference id for the root service object.
7. THE ReferenceTable SHALL provide `describe` returning each reference's id, type name, holder
   count and lease expiry.

### Requirement 3: Remote Proxy

**User Story:** As a caller, I want a proxy to behave like the object it stands for, so that
remote code reads like local code.

#### Acceptance Criteria

1. THE RemoteProxy SHALL forward attribute reads as RequestGetAttr and return the decoded value.
2. THE RemoteProxy SHALL forward attribute writes as RequestSetAttr and deletions as
   RequestDelAttr.
3. THE RemoteProxy SHALL forward calls as RequestCall with the attribute name, positional and
   keyword arguments, and SHALL return the decoded result or raise the decoded exception.
4. THE RemoteProxy SHALL support `__call__` on a proxy obtained from attribute access, so that
   `proxy.method(args)` performs exactly one round trip.
5. THE RemoteProxy SHALL forward `__len__`, `__iter__`, `__contains__`, `__getitem__`,
   `__setitem__`, `__delitem__`, `__enter__` and `__exit__` as calls to the corresponding dunder
   methods on the target.
6. THE RemoteProxy SHALL NOT forward `__repr__`; it SHALL return a local representation naming
   the remote type, reference id and peer session id.
7. THE RemoteProxy SHALL forward `__eq__` and `__hash__` based on reference id and session id so
   proxies to the same object compare equal.
8. WHEN a proxy is used after its session has closed, THE RemoteProxy SHALL raise
   `SessionClosedError`.
9. WHEN a request names a released or unknown reference, THE RemoteProxy SHALL raise
   `UnknownReferenceError` decoded from the peer's exception message.
10. THE RemoteProxy SHALL expose `remote_type_name`, `reference_id` and `session` as read-only
    properties, with names prefixed to avoid collision with the target's attributes.

### Requirement 4: Proxy Release

**User Story:** As an automation engineer running for hours, I want references to be released
when I stop using them, so that the far side does not accumulate objects.

#### Acceptance Criteria

1. WHEN a RemoteProxy is garbage collected, THE proxy layer SHALL send RequestRelease as a
   notification for its reference id.
2. THE proxy layer SHALL keep one RemoteProxy per reference id per session, so that decoding the
   same reference twice yields the same proxy and release is sent once.
3. WHEN the session closes, THE proxy layer SHALL mark every proxy closed without sending
   releases.
4. THE proxy layer SHALL provide an explicit `release()` method on the proxy for callers who do
   not want to depend on garbage collection.

### Requirement 5: Typed Service Proxy

**User Story:** As a client author, I want `get_service` to return something my IDE and type
checker understand, so that misuse is caught before the test runs.

#### Acceptance Criteria

1. THE client SHALL provide `get_service() -> ServiceProtocol` where `ServiceProtocol` is the
   type variable bound at client construction.
2. THE returned object SHALL be a RemoteProxy for the root reference id.
3. WHEN the service protocol type declares methods, THE RemoteProxy SHALL forward only names
   that exist on the protocol and SHALL raise `AttributeError` locally for others, so that typos
   fail without a round trip.
