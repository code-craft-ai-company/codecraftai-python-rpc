# Implementation Plan: Entry Points

## Overview

Rewrite the two entry point modules on top of the completed Sessions, Object Proxies and
Aspects features. The end-to-end test in task 4 is the milestone that makes the package usable.

## Tasks

- [x] 1. Initial entry point sketches
  - [x] 1.1 `RpcSocketServer` binds, listens and accepts; `RpcSocketClient` holds its endpoint (both non-functional beyond that)

- [x] 2. Server
  - [x] 2.1 Constructor with service instance, aspects, upgrader, callbacks; root registration per session
    - _Requirements: 1.1, 1.2_
  - [x] 2.2 `start`, `serve_forever`, `stop`, session table maintenance, context manager, `describe`
    - _Requirements: 2.1–2.7_
  - [x] 2.3 Properties including `bound_endpoint`; bind failure message
    - _Requirements: 1.3, 1.4_
  - [x] 2.4 `advertise` and `endpoints.py` types
    - _Requirements: 5.2, 5.3_
  - [x] 2.5 Tests: port zero, start and stop, multiple clients, session table shrink, callbacks fired
    - _Requirements: 1.3, 2.1–2.7_

- [x] 3. Client
  - [x] 3.1 Constructor with protocol type, endpoint or provider, aspects, upgrader
    - _Requirements: 3.1, 5.1_
  - [x] 3.2 `connect` retry loop, `ConnectionTimeout`, re-connect error, `close`, context manager, properties
    - _Requirements: 3.2–3.7_
  - [x] 3.3 `get_service` typed root proxy, before-connect error, `ping`
    - _Requirements: 4.1, 4.2, 4.3_
  - [x] 3.4 Tests: retry count and message, provider per attempt, double connect, get_service before connect, ping value
    - _Requirements: 3.2–3.4, 4.1–4.3, 5.1_

- [x] 4. End-to-end milestone
  - [x] 4.1 `test_end_to_end.py`: method call, remote exception, `ByRef` listener callback while a call is outstanding, clean stop
    - _Requirements: 1.2, 2.1, 3.2, 4.1_

- [x] 5. Package surface
  - [x] 5.1 `ccai/rpc/__init__.py` re-exports; update README and user guide examples to the working API

- [x] 6. Checkpoint - Ensure all tests pass
