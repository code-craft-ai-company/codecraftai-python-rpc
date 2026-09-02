# Requirements Document — Leases

## Introduction

The Leases feature ensures that objects and sessions held by a peer that has died or lost
connectivity are reclaimed. Explicit release messages handle the polite case; leases handle the
case where the holder never gets to send one. Every reference handed to a peer carries a lease
that the holder renews in bulk on the heartbeat. When renewals stop, the owner expires the
references and, if configured, notifies the owning service so it can reset the resource. The
same heartbeat proves the session itself is alive. The feature depends on Sessions and Object
Proxies and provides the primitive that resource checkout in higher packages builds on.

## Glossary

- **Lease**: A grant to hold a reference for `lease_duration` seconds from the last renewal.
- **Renewal**: A RequestRenew carrying every reference id the holder still uses, sent on the
  heartbeat interval.
- **Expiry**: The moment `lease_duration` has elapsed since the last renewal on the owner's
  clock.
- **Grace period**: The margin between the renewal interval and the lease duration that
  tolerates a missed heartbeat.
- **Lapse callback**: A callable the owning service registers to be invoked when a reference
  expires.
- **LeaseExpiredError**: The `codecraftai-errors` exception raised when a request names an
  expired reference.

## Requirements

### Requirement 1: Reference Leases

**User Story:** As a service author, I want objects held by a dead client to be released
automatically, so that a long-running service does not leak.

#### Acceptance Criteria

1. WHEN a reference is encoded to a peer, THE ReferenceTable SHALL record a lease expiring
   `lease_duration` seconds from now on the owner's clock.
2. WHEN a RequestRenew arrives, THE ReferenceTable SHALL extend the lease of every listed
   reference the peer holds to `lease_duration` seconds from now.
3. WHEN a RequestRenew lists a reference the peer does not hold, THE Session SHALL include that
   id in the ReplyRenew's `unknown` list so the holder can discard its proxy.
4. THE Session SHALL scan for expired leases at least every `lease_duration / 2` seconds and
   SHALL release each expired reference as if the holder had sent RequestRelease.
5. WHEN a request names an expired reference, THE Session SHALL answer with an ExceptionMessage
   of code LEASE_EXPIRED whose text names the reference type, id and last renewal time.
6. THE root service reference SHALL NOT be subject to lease expiry.
7. THE lease duration SHALL be at least twice the heartbeat interval, and THE Session SHALL raise
   `SemanticError` at start if the aspects violate this.

### Requirement 2: Renewal

**User Story:** As a client author, I want renewals to cost nothing per object, so that holding
thousands of references does not create heartbeat traffic proportional to that count.

#### Acceptance Criteria

1. THE holder Session SHALL send one RequestRenew per heartbeat interval listing every live
   proxy's reference id, in place of RequestPing when there are proxies to renew.
2. THE holder Session SHALL send RequestRenew even when other traffic has flowed, since traffic
   does not imply every reference was used.
3. WHEN ReplyRenew lists unknown ids, THE holder Session SHALL mark the corresponding proxies
   expired so their next use raises `LeaseExpiredError` locally.
4. THE lease duration SHALL be advertised by the server in ReplyHello, and THE client SHALL
   derive its renewal interval as one third of it unless its aspects specify a shorter one.

### Requirement 3: Session Leases

**User Story:** As an operator, I want a session whose peer has gone silent torn down, so that
its threads, references and sockets are reclaimed.

#### Acceptance Criteria

1. WHEN no frame has arrived within `inactivity_timeout`, THE Session SHALL expire every
   reference held by the peer, invoke lapse callbacks, and tear down as specified in Sessions.
2. THE Session SHALL treat any received frame as proof of liveness for the session lease, and
   only RequestRenew as proof of liveness for reference leases.

### Requirement 4: Lapse Callbacks

**User Story:** As a service author managing devices, I want to know when a holder disappears,
so that I can release the device or roll back what it was doing.

#### Acceptance Criteria

1. THE Session SHALL provide `on_lease_lapse(callback)` registering a callable invoked with the
   reference id, the object and the peer session id when a lease expires or a session lease
   ends.
2. THE Session SHALL invoke lapse callbacks on a dispatch worker, never on the heartbeat thread.
3. WHEN a lapse callback raises, THE Session SHALL log the exception and continue with the
   remaining callbacks.
4. THE package SHALL provide an `ILeaseAware` protocol with `on_lease_lapsed(peer_session_id)`
   that the Session calls on the object itself when it implements the protocol.

### Requirement 5: Observability

**User Story:** As an automation engineer, I want lease state visible, so that a reference that
went away can be explained.

#### Acceptance Criteria

1. THE ReferenceTable `describe` SHALL include each reference's lease expiry and last renewal
   time.
2. THE Session SHALL log every lease expiry at warning level with the reference type, id, peer
   session id and seconds since last renewal.
3. THE Session SHALL log session lease expiry at warning level with the seconds since the last
   frame.
