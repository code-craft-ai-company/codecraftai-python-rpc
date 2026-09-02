# Implementation Plan: Transport

## Overview

Replace `duplexsocketio.py`, whose send path writes null bytes and whose receive path raises on
every frame, with a `transport` package under `source/packages/ccai/rpc/core/`. The interface
and socket implementation come first, then the in-process helper, then wrappers.

## Tasks

- [x] 1. Initial socket wrapper
  - [x] 1.1 `DuplexSocketIO` with size-prefixed send and receive (both paths defective)

- [ ] 2. Transport interface
  - [ ] 2.1 Create `transport/base.py` with `Transport` and `TransportWrapper`
    - _Requirements: 1.1, 1.2, 1.3, 4.1, 4.4_
  - [ ] 2.2 Tests: abstract methods raise, wrapper forwards every operation
    - _Requirements: 1.2, 4.1_

- [ ] 3. Socket transport
  - [ ] 3.1 Create `transport/socketio.py`; `sendall` of size plus message under a send lock
    - _Requirements: 1.4, 2.1_
  - [ ] 3.2 `_recv_exact` with a preallocated buffer; `TransportClosedError` with byte counts
    - _Requirements: 2.2, 2.3_
  - [ ] 3.3 Size limit check, receive timeout preserving partial data, `TCP_NODELAY`, addresses, `close`
    - _Requirements: 2.4, 2.5, 2.6, 2.7, 2.8_
  - [ ] 3.4 Tests: round trip, multi-receive large frame, mid-frame close, oversize, timeout, closed transport
    - _Requirements: 2.1–2.8_

- [ ] 4. In-process transport
  - [ ] 4.1 Create `transport/inprocess.py` with `create_socketpair_transports`
    - _Requirements: 3.1, 3.2, 3.3_
  - [ ] 4.2 Tests: pair round trip in both directions
    - _Requirements: 3.1, 3.2_

- [ ] 5. Fault injection
  - [ ] 5.1 Create `transport/faults.py` with drop, delay, truncate, close-after and the action log
    - _Requirements: 4.2, 4.3_
  - [ ] 5.2 Tests: each fault applied once and recorded
    - _Requirements: 4.2, 4.3_

- [ ] 6. Remove `duplexsocketio.py` and update sessions and entry points

- [ ] 7. Checkpoint - Ensure all tests pass
