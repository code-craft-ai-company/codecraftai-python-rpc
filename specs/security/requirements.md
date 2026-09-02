# Requirements Document — Security

## Introduction

The Security feature protects an RPC endpoint that, by design, executes method calls on
request. It provides TLS as a transport upgrade, a token handshake at connect time, and the
guarantees that no decode path executes code and that a peer cannot reach objects it was not
given. Lab networks are not trusted networks; a service that accepts connections must be able
to insist on both encryption and authentication. The feature depends on Transport, Sessions and
Serialization.

## Glossary

- **Transport upgrader**: A callable that wraps a connected socket, used here to apply TLS.
- **Credential**: Bytes sent in RequestHello that the server validates.
- **Authenticator**: A server-side callable that accepts the credential and peer address and
  returns an identity or raises.
- **Identity**: A string naming the authenticated peer, attached to the session and the call
  context.
- **UnauthorizedError**: The `codecraftai-errors` exception raised when authentication fails.

## Requirements

### Requirement 1: TLS

**User Story:** As an operator, I want RPC traffic encrypted and the server verified, so that
credentials and results cannot be read or altered on the wire.

#### Acceptance Criteria

1. THE package SHALL provide `tls_server_upgrader(ssl_context)` and
   `tls_client_upgrader(ssl_context, server_hostname)` returning transport upgraders.
2. THE upgraders SHALL wrap the socket before any frame is exchanged and SHALL raise the
   `ssl.SSLError` from a failed handshake to the caller of `connect` or to the server's accept
   loop, which SHALL log it and continue.
3. THE client upgrader SHALL verify the server certificate and hostname by default, and THE
   package SHALL require an explicit `verify=False` argument to disable it.
4. THE package SHALL provide `mutual_tls_server_upgrader(ssl_context)` that requires a client
   certificate and exposes its subject as the session identity.
5. THE Transport `upgrade` hook SHALL preserve `local_address` and `remote_address`.

### Requirement 2: Token Handshake

**User Story:** As a service author, I want to accept only clients that know a shared secret,
so that anything on the network cannot call my service.

#### Acceptance Criteria

1. THE RpcSocketClient SHALL accept `credential: bytes` at construction and SHALL send it in
   RequestHello.
2. THE RpcSocketServer SHALL accept an `authenticator` callable, and WHEN one is set THE server
   session SHALL call it with the credential and peer address before answering RequestHello.
3. WHEN the authenticator raises or returns `None`, THE server session SHALL answer with an
   ExceptionMessage of code UNAUTHORIZED, log the failure with the peer address, and close the
   transport.
4. WHEN the authenticator returns an identity, THE server session SHALL expose it as
   `peer_identity` and include it in the call context and log records.
5. THE package SHALL provide `shared_secret_authenticator(secret)` that compares in constant
   time.
6. THE client SHALL raise `UnauthorizedError` from `connect` when the server rejects it.
7. THE server SHALL apply the connection timeout to the HELLO exchange so an unauthenticated
   peer cannot hold a session open indefinitely.

### Requirement 3: Safe Decoding and Reference Isolation

**User Story:** As a security reviewer, I want assurance that a peer cannot execute code or reach
objects beyond what it was handed, so that the RPC layer is not an arbitrary code execution
surface.

#### Acceptance Criteria

1. THE codec SHALL NOT use `pickle`, `marshal`, `eval`, `exec` or dynamic import on any decode
   path, and a test SHALL assert those names do not appear in the serialization package.
2. THE server SHALL resolve requests only against references its own table has issued to that
   peer session, and SHALL answer UNKNOWN_REFERENCE for any other id including ids issued to a
   different session.
3. THE server SHALL refuse GETATTR, SETATTR, DELATTR and CALL for attribute names beginning
   with an underscore unless the target type is decorated with `expose_private`.
4. THE server SHALL refuse SETATTR and DELATTR on the root service object unless the service
   type is decorated with `mutable_service`.
5. THE Wire Protocol maximum message size SHALL be configurable per server so that an operator
   can bound memory used by a single frame.

### Requirement 4: Audit

**User Story:** As an operator, I want authentication events recorded, so that access to a
service can be reviewed.

#### Acceptance Criteria

1. THE server SHALL log every successful authentication at info level and every failure at
   warning level with peer address, identity when known, and session id.
2. THE server SHALL log every UNKNOWN_REFERENCE and refused private-attribute access at warning
   level with the peer identity.
