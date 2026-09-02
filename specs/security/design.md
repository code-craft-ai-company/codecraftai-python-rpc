# Design Document — Security

## Overview

Security is layered on the existing seams: TLS is a transport upgrader, authentication is a
step in the HELLO exchange, and reference isolation is a check in the request handlers. The
serialization feature already excludes code execution; this feature adds the test that keeps it
that way.

## Architecture

### Connection Establishment

```
client                                  server
------                                  ------
TCP connect
tls_client_upgrader(transport) <------> tls_server_upgrader(transport)     (handshake)
RequestHello(version range, session id,
             credential, context)  -->  authenticator(credential, addr) -> identity | raise
                                   <--  ReplyHello(version, session id, lease)  or
                                        ExceptionMessage(UNAUTHORIZED); close
```

Both upgraders wrap `socket.socket` with `ssl.SSLContext.wrap_socket` and hand the result back
to `DuplexSocketIO`. Mutual TLS extracts the peer certificate subject as the identity, and the
authenticator, if also set, may refine or reject it.

### Reference Isolation

The reference table records which peer session each holder is. Handlers call
`table.resolve_for(peer_session_id, ref_id)`, which fails for ids issued to other peers. The
root id is exempt because every peer receives it.

### Attribute Policy

A small policy object consulted by the GETATTR, SETATTR, DELATTR and CALL handlers:

- underscore names refused unless the type carries the `expose_private` marker
- writes to the root refused unless the service type carries the `mutable_service` marker

### Design Decisions

1. **TLS as an upgrader** — sessions and entry points stay unaware; tests can run without it.
2. **Verify by default** — disabling verification must be a visible, deliberate choice at the
   call site.
3. **Authenticator callable** — the package does not choose an identity system; it provides the
   hook and one constant-time shared-secret implementation.
4. **Reject before HELLO reply** — an unauthenticated peer never learns the version, session id
   or lease policy.
5. **Per-peer reference resolution** — a client cannot guess or reuse another client's
   reference ids.
6. **Private names refused** — proxies should not reach implementation details; opting in is a
   type-level decision.
7. **Source-level test for forbidden names** — cheap and effective at preventing a future
   convenience from reintroducing pickle.

## Components and Interfaces

### File Layout

```
source/packages/ccai/rpc/security/__init__.py
source/packages/ccai/rpc/security/tls.py             tls_server_upgrader, tls_client_upgrader, mutual_tls_server_upgrader
source/packages/ccai/rpc/security/auth.py            Authenticator type, shared_secret_authenticator
source/packages/ccai/rpc/security/policy.py          AttributePolicy, expose_private, mutable_service
source/tests/test_security_tls.py
source/tests/test_security_auth.py
source/tests/test_security_isolation.py
source/tests/test_security_no_pickle.py
```

### Interfaces

```python
Authenticator = Callable[[bytes, Tuple[str, int]], Optional[str]]

def tls_server_upgrader(context: ssl.SSLContext) -> Callable[[Transport], None]
def tls_client_upgrader(context: ssl.SSLContext, server_hostname: str, verify: bool = True) -> Callable[[Transport], None]
def mutual_tls_server_upgrader(context: ssl.SSLContext) -> Callable[[Transport], None]
def shared_secret_authenticator(secret: bytes) -> Authenticator
def expose_private(cls: type) -> type
def mutable_service(cls: type) -> type
```

## Testing Strategy

TLS tests generate a self-signed certificate in the test's temporary directory, run a server
and client over it, and assert the handshake succeeds with verification against the generated
CA and fails against the default store. Auth tests assert a correct secret connects, a wrong one
yields `UnauthorizedError` and a warning log, and the identity appears in the call context.
Isolation tests connect two clients and assert one cannot use the other's reference id, that
underscore attributes are refused, and that root writes are refused without the marker. The
no-pickle test scans the serialization package source for the forbidden names.
