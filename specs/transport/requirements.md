# Requirements Document — Transport

## Introduction

The Transport feature moves framed messages between two endpoints. It defines a transport
interface that sessions program against, a socket implementation that guarantees complete
frames are written and read, an in-process implementation built on a socket pair for testing
the whole stack without a network, and the hooks that TLS and fault-injection wrappers use. The
transport has no knowledge of message contents; it deals only in frames as defined by the Wire
Protocol feature.

## Glossary

- **Transport**: The interface with `send_frame`, `receive_frame`, `close` and identity
  properties that a session uses.
- **DuplexSocketIO**: The `Transport` implementation over a connected TCP socket.
- **SocketPairTransport**: A `Transport` pair connected in-process through `socket.socketpair`.
- **Complete read**: Reading exactly the number of bytes a frame announces, looping over partial
  reads, and failing if the peer closes mid-frame.
- **TransportClosedError**: The `ccai.errors` exception raised when an operation is
  attempted on a closed transport or the peer closed the connection.
- **Fault injector**: A `Transport` wrapper that drops, delays or corrupts frames for tests.

## Requirements

### Requirement 1: Transport Interface

**User Story:** As a session author, I want to program against one transport interface, so that
sessions run unchanged over TCP, TLS or an in-process pair.

#### Acceptance Criteria

1. THE Transport interface SHALL define `send_frame(message: bytes) -> None`,
   `receive_frame() -> bytes`, `close() -> None`, and read-only `local_address`,
   `remote_address` and `is_open` properties.
2. THE Transport interface SHALL be an abstract base class whose abstract methods raise
   `AbstractMethodError` when not overridden.
3. THE Transport interface SHALL define `receive_frame` as blocking until a full frame is
   available or the transport is closed.
4. THE Transport interface SHALL allow one thread to call `send_frame` while another calls
   `receive_frame` concurrently, and SHALL serialise concurrent `send_frame` calls with a lock.

### Requirement 2: Socket Transport

**User Story:** As an automation engineer, I want the socket transport to deliver every byte of
every message or fail loudly, so that a partial write or read never turns into a corrupted call.

#### Acceptance Criteria

1. THE DuplexSocketIO SHALL send a frame as the 8 byte size followed by the message bytes using
   `sendall`, so that partial writes are handled by the socket layer.
2. THE DuplexSocketIO SHALL read the 8 byte size with a complete read and then read exactly that
   many message bytes with a complete read, looping over partial receives.
3. WHEN the peer closes the connection before a frame is complete, THE DuplexSocketIO SHALL
   raise `TransportClosedError` stating how many bytes were expected and received.
4. WHEN a frame size exceeds the Wire Protocol maximum, THE DuplexSocketIO SHALL raise
   `ProtocolError` and close the socket.
5. THE DuplexSocketIO SHALL accept an optional receive timeout, and WHEN no bytes arrive within
   it, `receive_frame` SHALL raise `TimeoutError` without discarding partially read data.
6. THE DuplexSocketIO SHALL set `TCP_NODELAY` on the socket so small request frames are not
   delayed by Nagle's algorithm.
7. THE DuplexSocketIO SHALL provide `close` that shuts down both directions and closes the
   socket, and SHALL make subsequent `send_frame` and `receive_frame` calls raise
   `TransportClosedError`.
8. THE DuplexSocketIO SHALL report the socket's local and peer addresses as `(host, port)`
   tuples.

### Requirement 3: In-Process Transport

**User Story:** As a test author, I want to connect a client session and a server session in
one process, so that the full stack can be tested quickly and deterministically.

#### Acceptance Criteria

1. THE package SHALL provide a `create_socketpair_transports()` function returning two connected
   `Transport` instances.
2. THE in-process transports SHALL behave identically to DuplexSocketIO for framing, closure and
   timeouts.
3. THE in-process transports SHALL work on Linux, macOS and Windows.

### Requirement 4: Transport Wrappers

**User Story:** As a maintainer, I want TLS and fault injection to be transport wrappers, so
that sessions stay unaware of them and tests can exercise failure paths.

#### Acceptance Criteria

1. THE package SHALL provide a `TransportWrapper` base class that forwards every `Transport`
   operation to an inner transport.
2. THE package SHALL provide a `FaultInjectingTransport` wrapper that can be configured to drop
   the next N frames, delay frames by a duration, truncate a frame, or close after N frames.
3. THE FaultInjectingTransport SHALL record every action it took so a test can assert on it.
4. THE Transport interface SHALL expose an `upgrade` hook that the Security feature uses to wrap
   a connected socket in TLS before any frame is exchanged.
