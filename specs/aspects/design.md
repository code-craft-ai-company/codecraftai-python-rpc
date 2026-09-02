# Design Document — Aspects

## Overview

`AspectsRpc` is a frozen dataclass-style object carrying every tunable in the package. It is
constructed once, passed to the client or server, and consulted by sessions, proxies and the
dispatch pool. Per-call variation is achieved by binding a proxy view to a different aspects
object, which keeps the remote method signatures untouched. The caller's timeout is forwarded
as a remaining-time value so the server can honour it.

## Architecture

### Where Aspects Are Read

```
AspectsRpc
  connection_timeout, max_attempts, completion_interval  -> RpcSocketClient.connect retry loop
  completion_timeout                                     -> RemoteProxy default request timeout,
                                                            deadline sent with each request
  heartbeat_interval, inactivity_timeout                 -> HeartbeatMonitor
  lease_duration                                         -> LeasePolicy (server side)
  dispatch_min_workers, dispatch_max_workers, highwater  -> session LooperPool
  logging_pattern, retry_logging_interval, logger_name   -> session and dispatch logging
```

### Override Resolution

For each request the proxy resolves aspects in this order: the proxy view's bound aspects, then
the thread-local scope set by `rpc_aspects_scope`, then the session default. The resolved
`completion_timeout` becomes both the local wait and the deadline sent in the request.

### Deadline Wire Format

The request carries `deadline_remaining: float` seconds. The receiver computes
`monotonic() + deadline_remaining` at unpack time and stores it in the call context. Absolute
timestamps are never sent, so clock skew cannot affect it.

### Design Decisions

1. **Derive from `ccai.aspects.Aspects`** — the minimal base keeps this package's dependency at
   `codecraftai-interfaces` rather than `codecraftai-interop`, matching the kubernetes and
   libvirt packages.
2. **Frozen** — defaults are module constants shared by every call; mutation would be a
   cross-call bug. `replace` provides the ergonomic path to variants.
3. **Validation at construction** — an invalid combination such as a lease shorter than two
   heartbeats fails when the aspects are defined, not minutes later when a lease expires
   spuriously.
4. **Proxy views for per-call override** — the remote method's signature is not ours to
   extend; a view avoids collisions and is explicit at the call site.
5. **Thread-local scope as a convenience** — useful for a block of calls, but the view is the
   primary mechanism because it is visible in the code.
6. **Remaining time, not absolute** — robust to skew, and cheap.
7. **`AspectsRpc` is `Flattenable`** — the first real by-value type, and useful when a service
   wants to run a sub-operation under the caller's aspects.

## Components and Interfaces

### File Layout

```
source/packages/ccai/rpc/aspects.py            AspectsRpc, DEFAULT_RPC_ASPECTS, rpc_aspects_scope, remaining_time
source/tests/test_aspects.py
source/tests/test_aspects_override.py
source/tests/test_aspects_deadline.py
```

### AspectsRpc

```python
class AspectsRpc(Aspects):
    def __init__(self, *,
                 completion_interval: float = 2.0,
                 completion_timeout: float = 600.0,
                 connection_timeout: float = 30.0,
                 max_attempts: int = 1,
                 logger_name: Optional[str] = None,
                 heartbeat_interval: float = 10.0,
                 inactivity_timeout: float = 60.0,
                 lease_duration: float = 90.0,
                 dispatch_min_workers: int = 2,
                 dispatch_max_workers: int = 8,
                 dispatch_highwater: int = 4,
                 logging_pattern: LoggingPattern = LoggingPattern.FAILURE_ONLY,
                 retry_logging_interval: float = 5.0) -> None
    def replace(self, **changes) -> "AspectsRpc"
    def flatten(self) -> dict
    @classmethod
    def unflatten(cls, data: dict) -> "AspectsRpc"

DEFAULT_RPC_ASPECTS = AspectsRpc()

@contextmanager
def rpc_aspects_scope(aspects: AspectsRpc) -> Iterator[None]

def remaining_time() -> Optional[float]
```

`LoggingPattern` is defined locally with the same values as `ccai.interop.aspects` to avoid the
dependency.

### RemoteProxy Extension

```python
def rpc_with_aspects(self, aspects: AspectsRpc) -> "RemoteProxy"
```

## Testing Strategy

Aspects tests cover defaults, immutability, each validation rule, `replace` and the
`Flattenable` round trip. Override tests run in-process sessions with a slow service method and
assert that a view with a short timeout raises `CompletionTimeout` while the default succeeds,
that the scope context manager applies to calls in the block only, and that views are not
cached. Deadline tests assert the remaining time arrives in the call context, that an already
expired deadline yields CANCELLED without invoking the handler, and that `remaining_time`
decreases inside a call.
