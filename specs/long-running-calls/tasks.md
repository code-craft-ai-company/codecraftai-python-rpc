# Implementation Plan: Long-Running Calls

## Overview

Add futures, cancellation and progress on top of Sessions, Callback Dispatch and Aspects. The
protocol messages CANCEL and PROGRESS already exist in the Wire Protocol vocabulary.

## Tasks

- [x] 1. Futures
  - [x] 1.1 Create `futures.py` with `RemoteFuture` over a session waiter; `Progress`; `wait_all`, `as_completed`
    - _Requirements: 1.2, 1.4, 1.6, 3.3_
  - [x] 1.2 `rpc_call_async` on `RemoteProxy`; completion from reply or exception; failure on session close
    - _Requirements: 1.1, 1.3, 1.5_
  - [x] 1.3 Tests: immediate return, result, exception, done callbacks, close fails futures, helpers
    - _Requirements: 1.1–1.6_

- [x] 2. Cancellation
  - [x] 2.1 Create `dispatch/cancel.py` with the correlation-id registry, `is_cancelled`, `check_cancelled`; deadline counts as cancelled
    - _Requirements: 2.2, 2.3, 2.6_
  - [x] 2.2 CANCEL handler; CANCELLED reply after a cancelled handler finishes
    - _Requirements: 2.4_
  - [x] 2.3 `RemoteFuture.cancel`; cancel on synchronous timeout
    - _Requirements: 2.1, 2.5_
  - [x] 2.4 Tests: cooperative loop stops, CANCELLED received, timeout sends cancel, deadline observed as cancelled
    - _Requirements: 2.1–2.6_

- [x] 3. Progress
  - [x] 3.1 `report_progress` sending RequestProgress notifications; error outside a call
    - _Requirements: 3.1, 3.6_
  - [x] 3.2 PROGRESS handling: route to the future, invoke callbacks on a worker, `last_progress`; liveness without deadline reset
    - _Requirements: 3.2, 3.4, 3.5_
  - [x] 3.3 Tests: callbacks on dispatch thread with increasing fractions, `last_progress`, outside-call error
    - _Requirements: 3.1–3.6_

- [x] 4. Checkpoint - Ensure all tests pass
