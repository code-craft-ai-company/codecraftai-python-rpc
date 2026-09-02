# Implementation Plan: Sessions

## Overview

Replace the two current session modules, which never start their threads and never complete a
waiter, with a `session` package built on the repaired Work Dispatch, the new Wire Protocol,
Serialization and Transport. Build the base class and request path first over the in-process
transport, then teardown, then heartbeat.

## Tasks

- [x] 1. Initial session sketches
  - [x] 1.1 `DuplexClientSession` and `DuplexServerSession` with thread and waiter fields (non-functional)

- [ ] 2. Session base and request path
  - [ ] 2.1 Create `session/base.py` with `DuplexSessionBase`, `Waiter`, the outbound `LooperQueue` and thread naming
    - _Requirements: 1.6, 4.1, 4.2, 6.1_
  - [ ] 2.2 `start`: pool, then receive thread, then transmit thread, each with a startup gate; raise on re-start
    - _Requirements: 1.1, 1.2_
  - [ ] 2.3 Receive loop: header-only routing, waiter completion, push REQUEST frames to the pool, inline PING reply
    - _Requirements: 3.1, 3.6_
  - [ ] 2.4 `send_request` with fresh correlation id, timeout, exception raising, code validation; `send_notification`, `send_reply`, `send_exception`
    - _Requirements: 2.1, 2.2, 2.3, 2.5, 2.6, 2.7, 2.8_
  - [ ] 2.5 Stray reply logging
    - _Requirements: 2.4_
  - [ ] 2.6 Tests over the in-process transport: correlation, exception propagation, timeout message, multiple outstanding, stray reply, wrong code
    - _Requirements: 2.1–2.7_

- [ ] 3. Dispatch
  - [ ] 3.1 Create `session/dispatch.py` with `DispatchLooper` and handler registry; PROTOCOL_ERROR for unknown codes
    - _Requirements: 3.2, 3.3, 3.4, 3.5_
  - [ ] 3.2 Tests: registered handler answers, raising handler yields ExceptionMessage, unknown code
    - _Requirements: 3.2–3.5_

- [ ] 4. HELLO and lifecycle
  - [ ] 4.1 Create `session/client.py` and `session/server.py`; client sends HELLO, server answers with chosen version and session id
    - _Requirements: 1.3_
  - [ ] 4.2 `_teardown(reason)` idempotent: fail waiters, shut pool, close transport, join threads; `close` sends RequestClose first
    - _Requirements: 1.4, 1.5, 4.3_
  - [ ] 4.3 Context manager, `describe`, lifecycle logging
    - _Requirements: 1.7, 6.2, 6.3_
  - [ ] 4.4 Tests: HELLO success and version rejection, close, peer close, send failure via fault injector, context manager
    - _Requirements: 1.1–1.7, 4.3_

- [ ] 5. Heartbeat
  - [ ] 5.1 Create `session/heartbeat.py` with `HeartbeatMonitor`; idle PING, inactivity teardown, timestamps
    - _Requirements: 5.1, 5.2, 5.3_
  - [ ] 5.2 Renewal hook for the Leases feature
    - _Requirements: 5.4_
  - [ ] 5.3 Tests with sub-second intervals: PING when idle, teardown and waiter failure on inactivity
    - _Requirements: 5.1–5.3_

- [ ] 6. Remove the old session modules and update entry points

- [ ] 7. Checkpoint - Ensure all tests pass
