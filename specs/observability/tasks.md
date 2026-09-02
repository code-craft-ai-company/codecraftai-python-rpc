# Implementation Plan: Observability

## Overview

Add the logging adapter and counters as soon as Sessions exist, then context propagation once
the header extension is in the Wire Protocol, then the state dump and wire trace.

## Tasks

- [x] 1. Logging adapter and patterns
  - [x] 1.1 Create `observability/logging.py`; session adapter with `session_id`, `peer_session_id`, `role`
    - _Requirements: 1.1, 1.6_
  - [x] 1.2 Lifecycle, warning and error logging in sessions; request outcome logging by pattern in dispatch
    - _Requirements: 1.2, 1.3, 1.4, 1.5_
  - [x] 1.3 Tests: attributes present, pattern selects records
    - _Requirements: 1.1–1.6_

- [x] 2. Counters
  - [x] 2.1 Create `observability/metrics.py`; counters in `describe`; sink on close
    - _Requirements: 5.1, 5.2_
  - [x] 2.2 Tests: counters increment, sink invoked
    - _Requirements: 5.1, 5.2_

- [x] 3. Caller context
  - [x] 3.1 Header extension in the Wire Protocol; context in RequestHello
    - _Requirements: 2.1_
  - [x] 3.2 `peer_context` on the server session and in its log records; `rpc_context_scope`; `caller_context` in the call context
    - _Requirements: 2.2, 2.3, 2.4_
  - [x] 3.3 Tests: context visible server side and in logs
    - _Requirements: 2.1–2.4_

- [x] 4. State and wire trace
  - [x] 4.1 Create `observability/state.py`; registry, `dump_state`, signal installer
    - _Requirements: 3.2, 3.3, 3.4_
  - [x] 4.2 Wire trace logger with hex excerpt and credential redaction
    - _Requirements: 4.1, 4.2, 4.3_
  - [x] 4.3 Tests: thread names, dump content, one trace record per frame, no credentials
    - _Requirements: 3.1–3.3, 4.1–4.3_

- [x] 5. Checkpoint - Ensure all tests pass
