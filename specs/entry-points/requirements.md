# Requirements Document — Entry Points

## Introduction

The Entry Points feature provides the two classes a user of `codecraftai-python-rpc` touches
directly: `RpcSocketServer`, which exposes a service object on an endpoint, and
`RpcSocketClient`, which connects to one and returns a typed proxy to the service. It covers
service registration, the accept loop and its shutdown, connection with retry, and the seams
through which discovery packages supply endpoints. It depends on Sessions, Object Proxies,
Aspects and Transport.

## Glossary

- **Service object**: The instance the server exposes as the root reference.
- **Service protocol**: The `typing.Protocol` or class describing the service's interface, used
  to type the client's proxy.
- **Endpoint**: A `(host, port)` tuple.
- **Accept loop**: The server thread that accepts connections and starts a session for each.
- **EndpointProvider**: A callable returning an endpoint, used so discovery can supply it lazily.
- **ConnectionTimeout**: The `ccai.errors` exception raised when connection attempts are
  exhausted.

## Requirements

### Requirement 1: Server Construction and Registration

**User Story:** As a service author, I want to hand the server an object and an endpoint, so
that exposing a service is one line.

#### Acceptance Criteria

1. THE RpcSocketServer SHALL accept a service object, an endpoint, an optional backlog, an
   optional `AspectsRpc` and an optional transport upgrader at construction.
2. THE RpcSocketServer SHALL register the service object as the root reference of every session
   it creates.
3. THE RpcSocketServer SHALL expose read-only `service`, `endpoint`, `bound_endpoint`,
   `aspects`, `is_serving` and `session_count` properties, where `bound_endpoint` reports the
   actual port when port zero was requested.
4. WHEN the endpoint cannot be bound, THE RpcSocketServer SHALL raise `OSError` with the
   endpoint in the message.

### Requirement 2: Serving and Stopping

**User Story:** As a test harness author, I want to start and stop the server from my own
code, so that it fits in a fixture.

#### Acceptance Criteria

1. THE RpcSocketServer SHALL provide `serve_forever` that binds, listens, accepts connections,
   wraps each in a transport and a `DuplexServerSession`, starts the session and returns only
   when `stop` is called.
2. THE RpcSocketServer SHALL provide `start` that runs `serve_forever` on a named background
   thread and returns once the socket is bound and listening.
3. THE RpcSocketServer SHALL provide `stop(timeout)` that stops accepting, closes every
   session, joins the accept thread and returns the number of sessions closed.
4. WHEN a session ends, THE RpcSocketServer SHALL remove it from its session table.
5. THE RpcSocketServer SHALL support use as a context manager that starts on entry and stops on
   exit.
6. THE RpcSocketServer SHALL provide `describe` returning the endpoint, serving state and each
   session's description.
7. THE RpcSocketServer SHALL accept an optional `on_session(session)` callback invoked on a
   dispatch worker when a session completes HELLO, and `on_session_closed(session, reason)`.

### Requirement 3: Client Construction and Connection

**User Story:** As a client author, I want a client that waits for the service to come up, so
that test setup does not need its own retry loop.

#### Acceptance Criteria

1. THE RpcSocketClient SHALL accept a service protocol type, an endpoint or `EndpointProvider`,
   an optional `AspectsRpc` and an optional transport upgrader at construction.
2. THE RpcSocketClient SHALL provide `connect(aspects=None)` that attempts a TCP connection with
   `connection_timeout` per attempt, retries up to `max_attempts` times waiting
   `completion_interval` between attempts, starts a `DuplexClientSession`, completes HELLO and
   returns.
3. WHEN every attempt fails, THE RpcSocketClient SHALL raise `ConnectionTimeout` naming the
   endpoint, the number of attempts and the last error.
4. WHEN `connect` is called on a connected client, THE RpcSocketClient SHALL raise
   `SessionError`.
5. THE RpcSocketClient SHALL provide `close(timeout)` that closes the session.
6. THE RpcSocketClient SHALL expose read-only `endpoint`, `aspects`, `is_connected` and
   `session` properties.
7. THE RpcSocketClient SHALL support use as a context manager that connects on entry and closes
   on exit.

### Requirement 4: Service Access

**User Story:** As a client author, I want a typed handle to the service, so that calls on it
are checked by my tools.

#### Acceptance Criteria

1. THE RpcSocketClient SHALL provide `get_service(aspects=None) -> ServiceProtocol` returning
   the root proxy, typed with the class's type variable.
2. WHEN `get_service` is called before `connect`, THE RpcSocketClient SHALL raise `SessionError`.
3. THE RpcSocketClient SHALL provide `ping(timeout=None) -> float` returning the round-trip time
   in seconds.

### Requirement 5: Endpoint Seams

**User Story:** As a landscaping author, I want to supply endpoints from discovery, so that
clients do not hard-code addresses.

#### Acceptance Criteria

1. THE RpcSocketClient SHALL accept an `EndpointProvider` callable and SHALL call it on each
   connection attempt, so that a changed address is picked up on retry.
2. THE package SHALL provide `IServiceEndpoint` in `ccai.rpc` with `host`, `port` and
   `service_name`, as the type discovery packages produce.
3. THE RpcSocketServer SHALL provide `advertise() -> IServiceEndpoint` describing itself for
   registration with discovery.
