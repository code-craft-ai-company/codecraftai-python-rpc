# Implementation Plan: Callback Dispatch

## Overview

Add ordering, call context, re-entrancy handling and delivery modes on top of the Sessions and
Object Proxies features. Nothing here can start until sessions exchange calls in-process.

## Tasks

- [ ] 1. Call context
  - [ ] 1.1 Create `dispatch/context.py` with `CallContext` and the thread-local accessor
    - _Requirements: 3.4, 5.1_
  - [ ] 1.2 Set and clear the context in `DispatchLooper.loop`; inherit the deadline in `send_request`
    - _Requirements: 3.3_
  - [ ] 1.3 Tests: context visible inside a callback, `None` elsewhere, deadline inherited
    - _Requirements: 3.3, 3.4_

- [ ] 2. Thread guarantees and pool sizing
  - [ ] 2.1 Size the dispatch pool from aspects; growth warning once per interval
    - _Requirements: 1.3, 1.4, 1.5_
  - [ ] 2.2 Tests: callbacks run on dispatch threads only; pool grows under a burst
    - _Requirements: 1.1, 1.2, 1.4_

- [ ] 3. Ordering lanes
  - [ ] 3.1 Create `dispatch/lanes.py` with `TargetLane` and `LaneTable`; drain-by-holder semantics
    - _Requirements: 2.1, 2.2_
  - [ ] 3.2 `concurrent_callbacks` decorator in `dispatch/decorators.py`; lane bypass
    - _Requirements: 2.3_
  - [ ] 3.3 Tests: in-order per target, interleaved across targets, bypass for decorated types
    - _Requirements: 2.1–2.3_

- [ ] 4. Re-entrancy
  - [ ] 4.1 Exhaustion timeout message including the pool description
    - _Requirements: 3.2_
  - [ ] 4.2 Tests: nested call completes; exhausted pools produce the timeout with diagnosis
    - _Requirements: 3.1, 3.2_

- [ ] 5. Delivery modes
  - [ ] 5.1 `rpc_notify` on `RemoteProxy`; `oneway` decorator; notification flag on RequestCall
    - _Requirements: 4.1, 4.2, 4.4_
  - [ ] 5.2 Handler suppresses replies for notifications and logs their exceptions
    - _Requirements: 4.3_
  - [ ] 5.3 Tests: notify returns immediately, exception logged not raised, decorated method uses notify
    - _Requirements: 4.2–4.4_

- [ ] 6. Diagnostics
  - [ ] 6.1 Busy-worker reporting in `describe`; long-callback warning
    - _Requirements: 5.2, 5.3_
  - [ ] 6.2 Tests: `describe` shows the executing callable; warning logged once
    - _Requirements: 5.2, 5.3_

- [ ] 7. Checkpoint - Ensure all tests pass
