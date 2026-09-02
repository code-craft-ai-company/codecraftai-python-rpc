# Implementation Plan: Observability

## Overview

Add the logging adapter and counters as soon as Sessions exist, then context propagation once
the header extension is in the Wire Protocol, then the state dump and wire trace.

## Tasks

- [ ] 1. Logging adapter and patterns
  - [ ] 1.1 Create `observability/logging.py`; session adapter with `session_id`, `peer_session_id`, `role`
    - _Requirements: 1.1, 1.6_
  - [ ] 1.2 Lifecycle, warning and error logging in sessions; request outcome logging by pattern in dispatch
    - _Requirements: 1.2, 1.3, 1.4, 1.5_
  - [ ] 1.3 Tests: attributes present, pattern selects records
    - _Requirements: 1.1–1.6_

- [ ] 2. Counters
  - [ ] 2.1 Create `observability/metrics.py`; counters in `describe`; sink on close
    - _Requirements: 5.1, 5.2_
  - [ ] 2.2 Tests: counters increment, sink invoked
    - _Requirements: 5.1, 5.2_

- [ ] 3. Caller context
  - [ ] 3.1 Header extension in the Wire Protocol; context in RequestHello
    - _Requirements: 2.1_
  - [ ] 3.2 `peer_context` on the server session and in its log records; `rpc_context_scope`; `caller_context` in the call context
    - _Requirements: 2.2, 2.3, 2.4_
  - [ ] 3.3 Tests: context visible server side and in logs
    - _Requirements: 2.1–2.4_

- [ ] 4. State and wire trace
  - [ ] 4.1 Create `observability/state.py`; registry, `dump_state`, signal installer
    - _Requirements: 3.2, 3.3, 3.4_
  - [ ] 4.2 Wire trace logger with hex excerpt and credential redaction
    - _Requirements: 4.1, 4.2, 4.3_
  - [ ] 4.3 Tests: thread names, dump content, one trace record per frame, no credentials
    - _Requirements: 3.1–3.3, 4.1–4.3_

- [ ] 5. Checkpoint - Ensure all tests pass
