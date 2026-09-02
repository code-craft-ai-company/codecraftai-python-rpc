# Design Document — Sessions

## Overview

A session binds one transport to three kinds of threads and a waiter table. It is symmetric:
client and server sessions share `DuplexSessionBase` and differ only in which side sends HELLO
and which handlers are registered. The receive thread is kept trivially simple so it can never
be the thing that blocks; all decoding and execution happens on dispatch workers or on the
caller's own thread.

## Architecture

### Threads and Queues

```
 caller threads          transmit thread          receive thread          dispatch workers
 --------------          ---------------          --------------          ----------------
 send_request()
   waiter = Waiter(cid)
   outbound.push(frame) -> pop; send_frame()  ... peer ...
   waiter.wait(timeout)                        receive_frame()
                                               header = unpack header
                                               REPLY/EXCEPTION -> waiters[cid].complete(frame)
   <-- returns reply                           REQUEST -> pool.push_work((session, frame))
                                                                          msg = unpack(frame)
                                                                          handler(msg)
                                                                          outbound.push(reply)
```

### Request Flow

1. `send_request` assigns a UUID, creates a `Waiter`, stores it under the id, packs the message
   and pushes the frame to the outbound queue.
2. The transmit thread sends the frame.
3. The peer's receive thread pushes the frame to its pool; a worker executes the handler and
   pushes a reply.
4. The local receive thread reads the reply header, finds the waiter by id, stores the frame in
   it and sets its event.
5. `send_request` wakes, unpacks the frame on the caller's thread, raises if it is an exception,
   validates the code and returns the reply.

Decoding replies on the caller's thread means the resolver for reference placeholders has the
calling context, and the receive thread never touches the serialization layer.

### Teardown

`_teardown(reason)` runs at most once, guarded by a lock. It marks the session closed, fails
every waiter with the given exception, shuts down the pool, closes the transport (which unblocks
the receive thread), pushes a sentinel to the outbound queue (which unblocks the transmit thread),
and joins both threads with a timeout. `close` sends RequestClose first and then calls
`_teardown(SessionClosedError)`.

### Heartbeat

A timer thread, `rpc-<role>-heartbeat-<id>`, wakes every `heartbeat_interval`. If nothing has
been sent in that interval it sends a PING notification. If nothing has been received in
`inactivity_timeout` it triggers `_teardown(InActivityTimeout)`. PING is answered on the receive
thread directly because it is trivial and must not queue behind slow callbacks.

### Design Decisions

0. **Replies to notifications are dropped quietly** — PING, RELEASE and other notifications are answered by the peer; their correlation ids are remembered so the reply is discarded without a stray-reply warning.

1. **Symmetric base class** — client and server sessions are the same machine; only HELLO
   direction and handler sets differ. This removes the duplicated code in the two current
   modules.
2. **Correlation by request id, not thread** — the current design keys waiters by thread guid,
   which forbids multiple outstanding calls per thread and breaks nested callbacks.
3. **Replies completed on the receive thread, decoded on the caller's thread** — completing a
   waiter is a dictionary lookup and an event set; nothing slow ever runs there.
4. **One FIFO outbound queue** — a `LooperQueue` reused from Work Dispatch, replacing the
   current list that is drained last-in first-out.
5. **Handlers registered by code** — other features add behaviour without subclassing the
   session, keeping the session's own surface small.
6. **Teardown is idempotent and always fails waiters** — a caller blocked in `send_request`
   must always wake with a specific exception naming why.
7. **Heartbeat is a session concern, leases ride on it** — one timer, one PING, and the Leases
   feature attaches renewal ids to it rather than running its own thread.

## Components and Interfaces

### File Layout

```
source/packages/ccai/rpc/core/session/__init__.py
source/packages/ccai/rpc/core/session/base.py        DuplexSessionBase, Waiter
source/packages/ccai/rpc/core/session/client.py      DuplexClientSession
source/packages/ccai/rpc/core/session/server.py      DuplexServerSession
source/packages/ccai/rpc/core/session/dispatch.py    DispatchLooper
source/packages/ccai/rpc/core/session/heartbeat.py   HeartbeatMonitor
source/packages/ccai/rpc/errors.py                   SessionError, SessionClosedError
source/tests/test_session_lifecycle.py
source/tests/test_session_requests.py
source/tests/test_session_heartbeat.py
```

The existing `duplexclientsession.py` and `duplexserversession.py` are replaced.

### DuplexSessionBase

```python
class DuplexSessionBase:
    def __init__(self, transport: Transport, role: str, aspects: AspectsRpc) -> None
    def start(self) -> None
    def close(self, timeout: Optional[float] = None) -> None
    def send_request(self, message: Message, timeout: Optional[float] = None) -> Message
    def send_notification(self, message: Message) -> None
    def send_reply(self, reply: Message) -> None
    def send_exception(self, exception_message: ExceptionMessage) -> None
    def register_handler(self, code: RequestCode, handler: Callable[[Message], Message]) -> None
    def describe(self) -> dict
    # properties: session_id, peer_session_id, is_running, protocol_version, remote_address,
    #             last_received_at, last_sent_at
```

### Waiter

```python
class Waiter:
    correlation_id: uuid.UUID
    request_code: RequestCode
    event: threading.Event
    frame: Optional[bytes]
    failure: Optional[BaseException]
    def complete(self, frame: bytes) -> None
    def fail(self, error: BaseException) -> None
```

### DispatchLooper

A `Looper` subclass whose `loop` receives `(session, frame)`, unpacks the message, resolves the
handler, and sends the reply or exception. It catches everything.

## Testing Strategy

Tests connect two sessions over the in-process transport. Lifecycle tests cover start ordering,
HELLO negotiation, version rejection, close, peer-close teardown and the context manager.
Request tests cover reply correlation, exception propagation, timeout with a specific message,
several outstanding requests from one thread, stray replies and mismatched codes. Heartbeat
tests use sub-second intervals to verify PING is sent when idle and that inactivity tears down
the session and fails waiters. A fault-injecting transport exercises the send-failure path.
