# Implementation Plan: Object Proxies

## Overview

Turn the current `ByRef` and `ByValue` data holders into a working reference system under
`source/packages/ccai/rpc/core/proxy/`. The table and wrappers come first because they have no
session dependency, then the proxy and handlers over the in-process session pair.

## Tasks

- [x] 1. Passing wrappers
  - [x] 1.1 `ByRef` with a reference id and `ByValue` holding an instance
    - _Requirements: 1.1, 1.2_

- [ ] 2. Reference table and wrappers
  - [ ] 2.1 Create `proxy/table.py` with `ReferenceTable`, holder counts, root id, `describe`
    - _Requirements: 2.1–2.7_
  - [ ] 2.2 Move wrappers to `proxy/wrappers.py`; `instance` properties; `by_ref` decorator; idempotent registration through the table
    - _Requirements: 1.1, 1.2, 1.4, 1.5_
  - [ ] 2.3 Tests: table behaviours, decorator, idempotence
    - _Requirements: 1.4, 1.5, 2.1–2.7_

- [ ] 3. Proxy cache and resolver
  - [ ] 3.1 Create `proxy/cache.py`; one proxy per reference id; weak references for release
    - _Requirements: 4.2_
  - [ ] 3.2 Session resolver: peer placeholders become proxies, own placeholders resolve to real objects
    - _Requirements: 3.1, 2.2_
  - [ ] 3.3 Tests: same placeholder yields same proxy; own object comes back as itself
    - _Requirements: 4.2_

- [ ] 4. Remote proxy
  - [ ] 4.1 Create `proxy/remoteproxy.py`; attribute get, set, delete; one-round-trip calls
    - _Requirements: 3.1, 3.2, 3.3, 3.4, 3.10_
  - [ ] 4.2 Dunder forwarding, local `repr`, equality and hash
    - _Requirements: 3.5, 3.6, 3.7_
  - [ ] 4.3 Closed-session and unknown-reference errors; protocol-filtered attributes
    - _Requirements: 3.8, 3.9, 5.3_
  - [ ] 4.4 Release on garbage collection and explicit `rpc_release`; no releases after close
    - _Requirements: 4.1, 4.3, 4.4_
  - [ ] 4.5 Unwrapped-object rejection before send
    - _Requirements: 1.3_

- [ ] 5. Owner-side handlers
  - [ ] 5.1 Create `proxy/handlers.py` and register GETATTR, SETATTR, DELATTR, CALL, RELEASE on session start
    - _Requirements: 3.1–3.3, 4.1_
  - [ ] 5.2 Typed `get_service` returning the root proxy
    - _Requirements: 5.1, 5.2_

- [ ] 6. End-to-end proxy tests over in-process sessions
  - _Requirements: 3.1–3.10, 4.1–4.4, 5.1–5.3_

- [ ] 7. Remove the old `proxy.py` module

- [ ] 8. Checkpoint - Ensure all tests pass
