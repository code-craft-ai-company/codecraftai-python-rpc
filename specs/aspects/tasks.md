# Implementation Plan: Aspects

## Overview

Add `ccai.rpc.aspects` and wire it into the client, server, session, proxy and dispatch code.
Task 1 has no dependencies and can be done early; tasks 2 through 4 follow Sessions, Object
Proxies and Callback Dispatch. `ccai.aspects` ships in `codecraftai-foundations`, which is already a dependency.

## Tasks

- [x] 1. AspectsRpc
  - [x] 1.1 `ccai.aspects` is available through the existing `codecraftai-foundations` dependency
  - [x] 1.2 Create `aspects.py` with `AspectsRpc`, `LoggingPattern`, validation, `replace`, `DEFAULT_RPC_ASPECTS`
    - _Requirements: 1.1, 1.2, 1.3, 1.4, 1.5, 1.6_
  - [x] 1.3 `Flattenable` implementation and registration (after Serialization task 4)
    - _Requirements: 1.7_
  - [x] 1.4 Tests: defaults, immutability, each validation failure, `replace`, flatten round trip
    - _Requirements: 1.1–1.7_

- [x] 2. Session defaults
  - [x] 2.1 `aspects` on client and server constructors and properties; sessions read pool sizes, heartbeat, inactivity, logging
    - _Requirements: 2.1, 2.2_
  - [x] 2.2 Connect retry loop driven by aspects; proxy default timeout from aspects
    - _Requirements: 2.3, 2.4_
  - [x] 2.3 Tests: pool sized from aspects; connect retries the configured number of times
    - _Requirements: 2.2, 2.3_

- [x] 3. Per-call override
  - [x] 3.1 `rpc_with_aspects` view on `RemoteProxy`; equality preserved; not cached; no release
    - _Requirements: 3.1, 3.2, 3.3_
  - [x] 3.2 Optional `aspects` on `connect` and `get_service`; `rpc_aspects_scope` thread-local
    - _Requirements: 3.4, 3.5_
  - [x] 3.3 Tests: short-timeout view raises while default succeeds; scope applies within block only
    - _Requirements: 3.1–3.5_

- [x] 4. Deadline propagation
  - [x] 4.1 Send `deadline_remaining` on attribute and call requests; compute absolute deadline in the call context
    - _Requirements: 4.1, 4.2_
  - [x] 4.2 CANCELLED for already expired deadlines; `remaining_time`
    - _Requirements: 4.3, 4.4_
  - [x] 4.3 Tests: deadline present in context, expired deadline not invoked, `remaining_time` decreases
    - _Requirements: 4.1–4.4_

- [x] 5. Checkpoint - Ensure all tests pass
