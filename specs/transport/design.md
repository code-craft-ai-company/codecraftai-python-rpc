# Design Document — Transport

## Overview

The transport layer is a thin, strict abstraction over a byte stream. Its job is to guarantee
that a frame handed to `send_frame` arrives whole at the peer's `receive_frame`, or that the
failure is reported with enough detail to diagnose. Everything above it, sessions and dispatch,
is written against the `Transport` interface so that TCP, TLS, an in-process pair and a
fault-injecting wrapper are interchangeable.

## Architecture

### Send and Receive Paths

```
send_frame(message)                     receive_frame()
  check is_open                           check is_open
  size = pack("!Q", len(message))         size_bytes = _recv_exact(8)
  with send_lock:                         size = unpack("!Q", size_bytes)
      sock.sendall(size + message)        check size <= MAX_MESSAGE_SIZE
                                          message = _recv_exact(size)
                                          return message
```

`_recv_exact(n)` loops on `recv_into` a preallocated buffer until `n` bytes are collected,
raising `TransportClosedError` on a zero-length read. Sending size and message in one `sendall`
avoids a second system call per frame.

### Wrappers

```
Session --> TransportWrapper (TLS / fault injection) --> DuplexSocketIO --> socket
```

A wrapper holds an inner transport and forwards by default. The fault injector overrides
`send_frame` and `receive_frame` to apply its configured behaviour and append to an action log.

### Design Decisions

1. **`sendall` for writes** — the current code loops on `send` and slices the wrong buffer.
   `sendall` handles partial writes correctly and is what every mature Python network library
   uses.
2. **Complete reads with a preallocated buffer** — `recv_into` a `bytearray` sized to the
   frame avoids repeated allocation; a zero-length read is the unambiguous close signal.
3. **One send lock, no receive lock** — the session guarantees a single receive thread, but
   several threads may want to send. Serialising sends keeps frames from interleaving.
4. **Timeouts are the socket's** — `receive_frame` sets the socket timeout; a `socket.timeout`
   between frames surfaces as `TimeoutError`; partially read bytes are kept in the instance so
   a retry continues the same frame.
5. **`socketpair` for in-process tests** — real socket semantics with no port allocation or
   firewall involvement, and it works on all three platforms since Python 3.5.
6. **Wrappers rather than flags** — TLS and fault injection compose without touching the socket
   implementation, and tests can stack a fault injector over a socket pair.

## Components and Interfaces

### File Layout

```
source/packages/ccai/rpc/core/transport/__init__.py
source/packages/ccai/rpc/core/transport/base.py          Transport, TransportWrapper
source/packages/ccai/rpc/core/transport/socketio.py      DuplexSocketIO
source/packages/ccai/rpc/core/transport/inprocess.py     create_socketpair_transports
source/packages/ccai/rpc/core/transport/faults.py        FaultInjectingTransport
source/tests/test_transport_socketio.py
source/tests/test_transport_inprocess.py
source/tests/test_transport_faults.py
```

The existing `duplexsocketio.py` is replaced by the `transport` package.

### Transport

```python
class Transport(ABC):
    @property
    def local_address(self) -> Tuple[str, int]
    @property
    def remote_address(self) -> Tuple[str, int]
    @property
    def is_open(self) -> bool
    def send_frame(self, message: bytes) -> None
    def receive_frame(self) -> bytes
    def close(self) -> None
    def upgrade(self, upgrader: Callable[[socket.socket], socket.socket]) -> None
```

### DuplexSocketIO

```python
class DuplexSocketIO(Transport):
    def __init__(self, sock: socket.socket, receive_timeout: Optional[float] = None) -> None
```

### FaultInjectingTransport

```python
class FaultInjectingTransport(TransportWrapper):
    def drop_next(self, count: int) -> None
    def delay_frames(self, seconds: float) -> None
    def truncate_next(self) -> None
    def close_after(self, count: int) -> None
    @property
    def actions(self) -> List[str]
```

## Testing Strategy

Socket tests use `socket.socketpair` directly and assert that a frame round-trips, that a
large frame spanning many receives arrives intact, that closing the peer mid-frame raises
`TransportClosedError` with the byte counts, that oversized frames are rejected, and that the
receive timeout raises without losing data. In-process tests confirm the helper returns two
transports that talk to each other. Fault tests confirm each configured fault is applied and
recorded.
