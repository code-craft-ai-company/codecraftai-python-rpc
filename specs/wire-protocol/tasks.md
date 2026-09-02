# Implementation Plan: Wire Protocol

## Overview

Replace the current `protocol.py`, whose `pack` methods fail for every message, with a
`protocol` package that has a fixed header, a message registry and symmetric pack and unpack.
Payload encoding depends on the Serialization feature's `encode` and `decode`; until that lands,
tasks 1 through 3 can proceed with header-only messages.

## Tasks

- [x] 1. Protocol vocabulary
  - [x] 1.1 Message type and request code constants; one class per request code
    - _Requirements: 3.1, 3.2_

- [x] 2. Constants and header
  - [x] 2.1 Create `protocol/constants.py` with versions, sizes and the four enums
    - _Requirements: 1.2, 3.1, 3.2, 3.3, 3.4, 5.1_
  - [x] 2.2 Create `protocol/header.py` with `MessageHeader.pack` and `unpack`
    - Correlation id as 16 raw bytes; reject short data, bad version, mismatched length
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 5.2_
  - [x] 2.3 Tests: header round trip, each rejection path
    - _Requirements: 2.1–2.4, 5.2_

- [x] 3. Message base class and registry
  - [x] 3.1 Create `protocol/messages.py` with `Message`, the `@message` decorator and the registry
    - _Requirements: 4.1, 4.2, 4.3, 3.5_
  - [x] 3.2 Payload-free messages: HELLO, PING, CLOSE, GETSERVICE and their replies
    - _Requirements: 4.8_
  - [x] 3.3 Tests: round trip and registry rejection of unknown pairs
    - _Requirements: 4.10, 3.5_

- [x] 4. Payload-carrying messages (after Serialization task 3)
  - [x] 4.1 Attribute requests and replies
    - _Requirements: 4.5, 4.6_
  - [x] 4.2 `RequestCall` and `ReplyCall` including the deadline
    - _Requirements: 4.4, 4.6_
  - [x] 4.3 `ExceptionMessage`
    - _Requirements: 4.7_
  - [x] 4.4 `RequestRelease`, `RequestRenew`, `RequestCancel`, `RequestProgress` and replies
    - _Requirements: 4.9_
  - [x] 4.5 Tests: round trip for every class with representative payloads
    - _Requirements: 4.10_

- [x] 5. Framing helpers
  - [x] 5.1 `frame(message_bytes)` and `read_frame_size(header_bytes)` helpers with the size limit
    - _Requirements: 1.1, 1.2, 1.3_
  - [x] 5.2 Tests: size limit and zero-length rejection
    - _Requirements: 1.2, 1.3_

- [x] 6. Remove the old `protocol.py` and update imports in sessions and entry points

- [x] 7. Checkpoint - Ensure all tests pass
