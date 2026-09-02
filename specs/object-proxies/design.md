# Design Document — Object Proxies

## Overview

Object Proxies gives each session a reference table on the owning side and a proxy cache on the
holding side, connected by the reference placeholders the Serialization feature encodes. A
`RemoteProxy` is a small object whose dunder methods build protocol requests and send them
through the session; everything else about the target lives with its owner. The service proxy
is just the proxy for a reserved root id.

## Architecture

### Reference Round Trip

```
owner side                                        holder side
----------                                        -----------
ByRef(listener)                                   
  table.register(listener) -> ref_id
  encode -> REFERENCE(ref_id, session_id, type)   decode(resolver)
                                                    cache.get(ref_id) or RemoteProxy(...)
                                                  proxy.on_event(x)
                                                    RequestCall(ref_id, "on_event", (x,), {})
  table.resolve(ref_id) -> listener               
  listener.on_event(x) on a dispatch worker       
  ReplyCall(result)                               <- returns result
                                                  del proxy  ->  RequestRelease(ref_id)
  table.release(ref_id)
```

### Resolver

Each session installs a resolver into `decode`. For a placeholder whose session id is the
peer's, it returns a proxy from the cache. For a placeholder whose session id is its own, the
object has come back home and the resolver returns the real object from the table. This makes
"pass a proxy back to its owner" work without special protocol support.

### Proxy Construction

`RemoteProxy` uses `__slots__` and defines `__getattr__` for names not in its own slots. Its own
state is exposed through properties prefixed with `rpc_` so they cannot collide with target
attributes. Method calls are one round trip: `__getattr__` returns a bound `_RemoteMethod`
callable that issues RequestCall with the attribute name, rather than first fetching the
attribute and then calling it.

### Design Decisions

1. **Holder counts plus release notifications** — prompt cleanup in the normal case. Leases are
   the backstop when the holder dies (see the Leases feature).
2. **One proxy per reference per session** — a cache keyed by reference id keeps `is` and `==`
   sensible and ensures exactly one release.
3. **Method call is one round trip** — fetching a method object and then calling it would double
   latency and require proxying bound methods.
4. **`__repr__` is local** — a debugger evaluating `repr` must never trigger network traffic.
5. **Protocol-aware attribute filtering** — when the service type is a `typing.Protocol`, the
   proxy validates names locally, turning a typo into an immediate `AttributeError`.
6. **`by_ref` class decorator** — listener and handle classes are almost always by reference;
   marking the class removes per-call wrapping noise while keeping the declaration visible.
7. **Reserved root id** — `get_service` needs no lookup; the root reference is UUID zero.

## Components and Interfaces

### File Layout

```
source/packages/ccai/rpc/core/proxy/__init__.py
source/packages/ccai/rpc/core/proxy/wrappers.py       ByRef, ByValue, by_ref
source/packages/ccai/rpc/core/proxy/table.py          ReferenceTable, ROOT_REFERENCE_ID
source/packages/ccai/rpc/core/proxy/remoteproxy.py    RemoteProxy, _RemoteMethod
source/packages/ccai/rpc/core/proxy/cache.py          ProxyCache
source/packages/ccai/rpc/core/proxy/handlers.py       GETATTR/SETATTR/DELATTR/CALL/RELEASE handlers
source/tests/test_proxy_wrappers.py
source/tests/test_proxy_table.py
source/tests/test_proxy_remote.py
```

The existing `proxy.py` becomes the `proxy` package.

### ReferenceTable

```python
class ReferenceTable:
    def register(self, obj: object) -> uuid.UUID
    def register_root(self, obj: object) -> None
    def resolve(self, ref_id: uuid.UUID) -> object
    def add_holder(self, ref_id: uuid.UUID) -> None
    def release(self, ref_id: uuid.UUID) -> None
    def release_all(self) -> None
    def describe(self) -> List[dict]
```

### RemoteProxy

```python
class RemoteProxy:
    __slots__ = ("_session", "_ref_id", "_type_name", "_protocol", "_closed", "__weakref__")
    rpc_reference_id: uuid.UUID
    rpc_remote_type_name: str
    rpc_session: DuplexSessionBase
    def rpc_release(self) -> None
    def __getattr__(self, name) -> object
    def __setattr__(self, name, value) -> None
    def __delattr__(self, name) -> None
    # __len__, __iter__, __contains__, __getitem__, __setitem__, __delitem__, __enter__, __exit__
    # __eq__, __hash__, __repr__
```

### Handlers

Registered on the session at start:

| Request  | Handler behaviour                                                        |
|----------|--------------------------------------------------------------------------|
| GETATTR  | `getattr(table.resolve(ref), name)` encoded; callables become references |
| SETATTR  | `setattr` with the decoded value                                         |
| DELATTR  | `delattr`                                                                |
| CALL     | `getattr(obj, name)(*args, **kwargs)` encoded                            |
| RELEASE  | `table.release(ref)`                                                     |

## Testing Strategy

Wrapper tests cover the properties, idempotent registration and the class decorator. Table
tests cover register, resolve, unknown id, holder counting, release to zero and `release_all`.
Proxy tests run two sessions in-process with a small service object: attribute read, write,
delete, call with arguments, remote exception, dunder forwarding, local `repr`, equality,
protocol-filtered attribute errors, release on `del`, and use after close. A test passes a
proxy back to its owner and asserts the owner receives the real object.
