# Implementation Plan: Serialization

## Overview

Build the codec under `source/packages/ccai/rpc/core/serialization/` bottom-up: tags and
scalars, then containers, then the registry-backed types, then exceptions and references. The
Wire Protocol's payload-carrying messages and Object Proxies both wait on this feature.

## Tasks

- [x] 1. Flattenable protocol stub
  - [x] 1.1 `Flattenable` with `flatten` raising `AbstractMethodError`
    - _Requirements: 2.5_

- [x] 2. Tags, versioning and scalars
  - [x] 2.1 Create `tags.py` with the `Tag` enum and `FORMAT_VERSION`
    - _Requirements: 5.2, 5.4_
  - [x] 2.2 Create `codec.py` with `Encoder` and `Decoder` for `None`, `bool`, `int`, `float`, `str`, `bytes`
    - Zigzag varint for `int`; `int` and `bool` distinguishable
    - _Requirements: 1.1, 1.2, 5.1_
  - [x] 2.3 Unknown type raises `SerializationError` with the value path
    - _Requirements: 1.4_
  - [x] 2.4 Tests: scalar round trips, version rejection, unknown type message
    - _Requirements: 1.1, 1.2, 1.4, 5.4, 5.5_

- [x] 3. Containers and time types
  - [x] 3.1 `list`, `tuple`, `dict`, `set`, `frozenset` with the depth limit
    - _Requirements: 1.1, 1.2, 1.5_
  - [x] 3.2 `datetime`, `date`, `timedelta`, `UUID`; naive datetime policy
    - _Requirements: 1.1, 1.3_
  - [x] 3.3 Tests: nested round trips, depth limit, naive datetime rejection
    - _Requirements: 1.3, 1.5, 5.5_

- [x] 4. Registry-backed types
  - [x] 4.1 Create `registry.py`; `register_enum`, `register_flattenable`, `register_dataclass`
    - _Requirements: 2.3, 2.6_
  - [x] 4.2 Extend `Flattenable` with `unflatten`; encode as tag plus dict
    - _Requirements: 2.1, 2.2, 2.4_
  - [x] 4.3 Tests: enum and Flattenable round trips, unregistered tag on decode, dataclass helper
    - _Requirements: 2.1–2.4, 2.6_

- [x] 5. Exceptions
  - [x] 5.1 Add `RemoteError` and re-export `SerializationError` in `ccai/rpc/errors.py`
    - _Requirements: 3.3_
  - [x] 5.2 Encode type name, message, args, traceback text; restricted type resolution on decode
    - _Requirements: 3.1, 3.2, 3.5_
  - [x] 5.3 Attach `remote_traceback` and include it in `__str__`
    - _Requirements: 3.4_
  - [x] 5.4 Tests: known ccai type, built-in type, unknown type, traceback present, no import triggered
    - _Requirements: 3.1–3.5_

- [x] 6. References
  - [x] 6.1 Create `placeholder.py`; encode `ByRef` as a placeholder; strip `ByValue`
    - _Requirements: 4.1, 4.4_
  - [x] 6.2 Resolver parameter on `decode`; error without resolver
    - _Requirements: 4.2, 4.3_
  - [x] 6.3 Tests: placeholder round trip, resolver called with placeholder, missing resolver error
    - _Requirements: 4.1–4.4_

- [x] 7. Checkpoint - Ensure all tests pass
