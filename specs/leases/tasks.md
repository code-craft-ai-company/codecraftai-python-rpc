# Implementation Plan: Leases

## Overview

Extend the reference table with lease state, attach renewal to the heartbeat, add the owner-side
sweep and the lapse callback path. Depends on Sessions task 5 (heartbeat) and Object Proxies
task 2 (reference table).

## Tasks

- [x] 1. Lease policy and table state
  - [x] 1.1 Create `leases/policy.py` with `LeasePolicy` derived from aspects; validate duration ≥ 2 × heartbeat
    - _Requirements: 1.7, 2.4_
  - [x] 1.2 Add `LeaseState` per holder to `ReferenceEntry`; `renew`, `expired`, `expire_peer`; root exemption
    - _Requirements: 1.1, 1.2, 1.6, 5.1_
  - [x] 1.3 Tests: renew extends, expired lists overdue entries, root never expires
    - _Requirements: 1.1, 1.2, 1.6_

- [x] 2. Renewal messages
  - [x] 2.1 RENEW handler in `leases/handlers.py`; ReplyRenew with unknown ids
    - _Requirements: 1.2, 1.3_
  - [x] 2.2 Holder side: heartbeat sends RequestRenew with live proxy ids; mark proxies expired from ReplyRenew
    - _Requirements: 2.1, 2.2, 2.3_
  - [x] 2.3 Advertise duration in ReplyHello; client derives renewal interval
    - _Requirements: 2.4_
  - [x] 2.4 Tests: renewals flow on the heartbeat, unknown ids expire proxies locally
    - _Requirements: 2.1–2.4_

- [x] 3. Expiry
  - [x] 3.1 Create `leases/sweeper.py`; sweep on the heartbeat thread at half the duration; release expired
    - _Requirements: 1.4_
  - [x] 3.2 LEASE_EXPIRED exception message on requests to expired references
    - _Requirements: 1.5_
  - [x] 3.3 Expiry logging
    - _Requirements: 5.2, 5.3_
  - [x] 3.4 Tests: paused heartbeat leads to expiry and the specific error text
    - _Requirements: 1.4, 1.5_

- [x] 4. Session lease integration
  - [x] 4.1 Expire the peer's references on inactivity teardown
    - _Requirements: 3.1, 3.2_
  - [x] 4.2 Tests: inactivity teardown expires references and fires lapse callbacks
    - _Requirements: 3.1_

- [x] 5. Lapse callbacks
  - [x] 5.1 `on_lease_lapse` registration; `ILeaseAware` in `leases/protocols.py`; invocation on a dispatch worker with exception isolation
    - _Requirements: 4.1, 4.2, 4.3, 4.4_
  - [x] 5.2 Tests: callback and `ILeaseAware` invoked on a dispatch thread; raising callback isolated
    - _Requirements: 4.1–4.4_

- [x] 6. Checkpoint - Ensure all tests pass
