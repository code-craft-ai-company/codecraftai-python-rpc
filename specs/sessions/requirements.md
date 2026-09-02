# Requirements Document — Sessions

## Introduction

The Sessions feature owns one connection between a client and a server. A session runs the
receive thread, the transmit thread and the dispatch pool for its transport, correlates replies
to waiting callers, propagates remote exceptions, detects a dead peer through heartbeats, and
closes cleanly. It is the layer where the package's central promise is kept: no callback ever
runs on the receive thread or on the thread that is blocked waiting for a reply. The feature
depends on Work Dispatch, Wire Protocol, Serialization and Transport, and is consumed by Object
Proxies, Callback Dispatch, Leases and the Entry Points.

## Glossary

- **Session**: The object owning one transport and its threads. `DuplexClientSession` and
  `DuplexServerSession` share a `DuplexSessionBase`.
- **Receive thread**: The thread that loops on `transport.receive_frame` and pushes each frame to
  the dispatch pool. It never decodes payloads.
- **Transmit thread**: The thread that drains the outbound queue onto the transport in order.
- **Dispatch pool**: The `LooperPool` whose workers decode and execute inbound messages.
- **Waiter**: The record of an outstanding request: its correlation id, an event, and a slot
  for the reply or exception.
- **Heartbeat**: A PING sent on a fixed interval when no other traffic is flowing, used for
  liveness and lease renewal.
- **Session id**: A UUID assigned by each side at HELLO, present in logs and reference
  placeholders.

## Requirements

### Requirement 1: Session Lifecycle

**User Story:** As an entry point author, I want a session to start its threads, negotiate with
the peer, and shut down cleanly, so that connections never hang half-open.

#### Acceptance Criteria

1. THE Session SHALL provide `start` that starts the dispatch pool, then the receive thread,
   then the transmit thread, and SHALL return only after all three are running.
2. WHEN `start` is called on a running or closed session, THE Session SHALL raise
   `SessionError`.
3. THE client Session SHALL send RequestHello immediately after `start` and SHALL raise
   `ProtocolError` if the reply does not select a supported version within the connection
   timeout.
4. THE Session SHALL provide `close` that sends RequestClose when the transport is open, stops
   accepting new requests, fails every outstanding waiter with `SessionClosedError`, shuts down
   the dispatch pool, closes the transport and joins its threads within a timeout.
5. WHEN the transport raises `TransportClosedError` on the receive thread, THE Session SHALL
   perform the same teardown as `close` without sending RequestClose.
6. THE Session SHALL expose read-only `session_id`, `peer_session_id`, `is_running`,
   `protocol_version` and `remote_address` properties.
7. THE Session SHALL support use as a context manager whose exit calls `close`.

### Requirement 2: Sending Requests and Correlating Replies

**User Story:** As a proxy author, I want to send a request and receive its reply or exception,
so that a remote call looks like a local call to the caller.

#### Acceptance Criteria

1. THE Session SHALL provide `send_request(message, timeout) -> Message` that assigns a fresh
   correlation id, registers a waiter, queues the frame for the transmit thread, blocks the
   calling thread until the reply or exception arrives, and returns the reply.
2. WHEN an ExceptionMessage arrives for a waiter, THE Session SHALL decode it and raise the
   resulting exception in the calling thread.
3. WHEN no reply arrives within the timeout, THE Session SHALL remove the waiter and raise
   `CompletionTimeout` naming the request code, target, callable and elapsed time.
4. WHEN a reply arrives whose correlation id has no waiter, THE Session SHALL log it at warning
   level and discard it.
5. WHEN a reply's code does not mirror the request's code, THE Session SHALL fail the waiter
   with `ProtocolError`.
6. THE Session SHALL allow one thread to have several requests outstanding at once.
7. THE Session SHALL provide `send_notification(message)` that queues a frame without
   registering a waiter, for fire-and-forget messages.
8. THE Session SHALL provide `send_reply(reply)` and `send_exception(exception_message)` used by
   dispatch workers to answer a request.

### Requirement 3: Receiving and Dispatching

**User Story:** As an automation engineer, I want inbound work to never block the socket, so
that a slow callback cannot stall replies to my other calls.

#### Acceptance Criteria

1. THE receive thread SHALL only read frames, unpack the header, and either complete a waiter
   for REPLY and EXCEPTION types or push the frame to the dispatch pool for REQUEST type.
2. THE dispatch worker SHALL unpack the full message, look up the handler for its request code,
   invoke it, and send the reply or an ExceptionMessage.
3. WHEN a handler raises, THE dispatch worker SHALL send an ExceptionMessage with the exception
   encoded and SHALL NOT let the exception reach the worker loop.
4. WHEN a request code has no handler, THE dispatch worker SHALL send an ExceptionMessage with
   code PROTOCOL_ERROR.
5. THE Session SHALL provide `register_handler(request_code, callable)` so Object Proxies,
   Leases and Long-Running Calls can add handlers without subclassing.
6. THE Session SHALL handle PING by replying ReplyPing without involving the dispatch pool.

### Requirement 4: Transmit Ordering

**User Story:** As a protocol implementer, I want frames sent in the order they were queued,
so that a reply never overtakes the request that caused it.

#### Acceptance Criteria

1. THE transmit thread SHALL drain the outbound queue first-in, first-out.
2. THE Session SHALL use one outbound queue for requests, replies, exceptions and heartbeats.
3. WHEN the transport raises on send, THE Session SHALL fail the corresponding waiter when there
   is one and SHALL begin teardown.

### Requirement 5: Heartbeat and Liveness

**User Story:** As an automation engineer, I want a dead peer detected in seconds, so that a
crashed host fails my test promptly instead of after a long call timeout.

#### Acceptance Criteria

1. THE Session SHALL send RequestPing every `heartbeat_interval` seconds when no frame has been
   sent in that interval.
2. WHEN no frame has been received for `inactivity_timeout` seconds, THE Session SHALL treat
   the peer as dead, fail every waiter with `InActivityTimeout`, and tear down.
3. THE Session SHALL expose `last_received_at` and `last_sent_at` timestamps.
4. THE heartbeat SHALL carry the lease renewals defined by the Leases feature when that feature
   is active.

### Requirement 6: Diagnostics

**User Story:** As an automation engineer, I want session state visible, so that a hung run
can be diagnosed from a thread dump and a log.

#### Acceptance Criteria

1. THE Session SHALL name its threads `rpc-<role>-recv-<short id>`, `rpc-<role>-xmit-<short id>`
   and dispatch workers `rpc-<role>-dispatch-<short id>-<n>`.
2. THE Session SHALL provide `describe` returning the session ids, running state, outstanding
   waiter count, outbound queue depth, pool description and last activity timestamps.
3. THE Session SHALL log connect, HELLO outcome, close reason and every teardown at info level,
   and every discarded or malformed frame at warning level, with the session id in each line.
