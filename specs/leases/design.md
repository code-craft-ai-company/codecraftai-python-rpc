# Design Document — Leases

## Overview

Leases add an expiry to every entry in the reference table and a renewal message to the
heartbeat. The owner never trusts a holder to release; it trusts renewals, and reclaims
anything not renewed. The mechanism is the one Java RMI and .NET Remoting used for distributed
garbage collection, simplified to bulk renewal on an interval the server chooses.

## Architecture

### Renewal Cycle

```
holder                                             owner
------                                             -----
heartbeat tick (every renewal_interval)
  ids = proxy_cache.live_ids()
  RequestRenew(ids)  ------------------------->   for id in ids: table.renew(id, now + duration)
                                                  unknown = ids - table.held_by(peer)
  <-------------------------------------------    ReplyRenew(unknown)
  for id in unknown: cache[id].mark_expired()

owner sweep (every duration / 2)
  for entry in table: if entry.expiry < now: table.release(id); fire lapse callbacks
```

### Clock Handling

All expiries are computed on the owner's clock from the arrival time of a renewal. Neither
side ever sends an absolute timestamp. The server advertises `lease_duration` in ReplyHello and
the client renews at one third of it, which gives two missed heartbeats before expiry.

### Session Lease

The session lease is the existing inactivity check in Sessions. This feature adds the reference
expiry and lapse callbacks to the inactivity teardown path, so a dead peer's references are
reclaimed on the same code path as a slow one's.

### Design Decisions

0. **Two small memories on the owner** — an expired reference leaves a tombstone so a later request gets `LeaseExpiredError` with the type and timing rather than an unknown-reference error, and a released object stays resolvable by its owner briefly so a reference returning home while its holder's release is in flight still resolves.

1. **Bulk renewal on the heartbeat** — one message per interval regardless of reference count.
2. **Server owns the duration** — the party that leaks is the one that should choose the
   policy; the client learns it at HELLO.
3. **Three renewals per duration** — a single dropped heartbeat cannot expire anything.
4. **Sweep at half the duration** — bounded staleness with negligible cost.
5. **Lapse callbacks on dispatch workers** — a service resetting a device may take seconds and
   must not stall the heartbeat.
6. **`ILeaseAware` protocol** — the object that represents a resource is usually the best place
   to put cleanup, and the protocol avoids a registration step for the common case.
7. **Root reference exempt** — the service object outlives every client by design.

## Components and Interfaces

### File Layout

```
source/packages/ccai/rpc/core/leases/__init__.py
source/packages/ccai/rpc/core/leases/policy.py        LeasePolicy (duration, renewal, sweep)
source/packages/ccai/rpc/core/leases/sweeper.py       LeaseSweeper
source/packages/ccai/rpc/core/leases/handlers.py      RENEW handler, lapse dispatch
source/packages/ccai/rpc/core/leases/protocols.py     ILeaseAware
source/tests/test_leases_renewal.py
source/tests/test_leases_expiry.py
source/tests/test_leases_lapse.py
```

### ReferenceTable Extensions

```python
class ReferenceEntry:
    ref_id: uuid.UUID
    obj: object
    holders: Dict[uuid.UUID, LeaseState]     # peer session id -> lease

class LeaseState:
    expires_at: float          # monotonic clock
    last_renewed_at: float

class ReferenceTable:
    def renew(self, peer: uuid.UUID, ref_ids: Iterable[uuid.UUID], duration: float) -> List[uuid.UUID]
    def expired(self, now: float) -> List[Tuple[uuid.UUID, uuid.UUID]]
    def expire_peer(self, peer: uuid.UUID) -> List[uuid.UUID]
```

### Session Extensions

```python
def on_lease_lapse(self, callback: Callable[[uuid.UUID, object, uuid.UUID], None]) -> None

class ILeaseAware(Protocol):
    def on_lease_lapsed(self, peer_session_id: uuid.UUID) -> None: ...
```

## Testing Strategy

Renewal tests use a sub-second lease duration over in-process sessions: a proxy kept alive
survives several durations; a proxy whose client stops renewing (simulated by pausing the
heartbeat) expires and the next call raises `LeaseExpiredError` with the expected text; a
renewal listing an unknown id marks the proxy expired locally. Expiry tests check the sweep
interval and root exemption. Lapse tests register a callback and an `ILeaseAware` object and
assert both are invoked on a dispatch thread after expiry and after session inactivity
teardown, and that a raising callback does not prevent the others.
