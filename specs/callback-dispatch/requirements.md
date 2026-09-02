# Requirements Document — Callback Dispatch

## Introduction

The Callback Dispatch feature defines the threading guarantees for requests that arrive from the
far side, including callbacks on `ByRef` objects. It is the reason this package exists: in
distributed automation a server frequently calls back into a listener the client passed it, and
if that callback lands on the thread the client is using to wait for a reply, the run deadlocks.
This feature specifies where callbacks execute, in what order, how re-entrant call chains are
handled, and how a caller chooses between acknowledged and fire-and-forget delivery. It depends
on Sessions, Work Dispatch and Object Proxies.

## Glossary

- **Callback**: A RequestCall, RequestGetAttr, RequestSetAttr or RequestDelAttr that arrives at
  a session for one of the objects it owns.
- **Dispatch worker**: A thread in the session's `LooperPool` that executes callbacks.
- **Re-entrant chain**: A call that causes a callback that itself makes a call, possibly
  causing a further callback, all before the original call returns.
- **Ordered target**: An object for which callbacks are executed one at a time in arrival
  order.
- **Acknowledged delivery**: A callback whose caller waits for the reply.
- **Fire-and-forget delivery**: A callback sent as a notification with no reply expected.
- **Call context**: Thread-local information about the request currently being executed by a
  dispatch worker: session, correlation id, caller session id, deadline.

## Requirements

### Requirement 1: Execution Thread Guarantees

**User Story:** As an automation engineer, I want a guarantee about which thread runs a
callback, so that I can reason about locks and blocking in my listener code.

#### Acceptance Criteria

1. THE Session SHALL execute every callback on a dispatch worker and never on the receive
   thread, the transmit thread or the heartbeat thread.
2. THE Session SHALL execute every callback on a thread distinct from any thread currently
   blocked in `send_request` on the same session.
3. THE dispatch pool SHALL be sized so that at least `min_loopers` callbacks can execute
   concurrently, with `min_loopers` and `max_loopers` taken from the session's aspects.
4. WHEN every dispatch worker is busy and the queue depth exceeds the high-water mark, THE
   Session SHALL grow the pool up to `max_loopers`.
5. WHEN the pool is at `max_loopers` and all workers are busy, THE Session SHALL queue further
   callbacks and SHALL log a warning naming the queue depth once per `retry_logging_interval`.

### Requirement 2: Ordering

**User Story:** As a listener author, I want events for the same object delivered in order, so
that state transitions are observed in the sequence they happened.

#### Acceptance Criteria

1. THE Session SHALL, by default, execute callbacks targeting the same reference id one at a
   time in arrival order.
2. THE Session SHALL execute callbacks targeting different reference ids concurrently.
3. THE package SHALL provide a `concurrent_callbacks` class decorator that marks a by-reference
   type as accepting concurrent callbacks, removing the per-target ordering for it.
4. THE Session SHALL make no ordering guarantee between a callback and a reply on the same
   session beyond frame transmission order.

### Requirement 3: Re-entrancy

**User Story:** As a service author, I want a callback to be able to call back into the service,
so that a listener can query the thing that notified it.

#### Acceptance Criteria

1. WHEN a dispatch worker executing a callback calls `send_request` on the same session, THE
   Session SHALL send the request and block only that worker, and SHALL continue to execute
   other callbacks on other workers.
2. WHEN a re-entrant chain reaches the maximum pool size on both sides, THE Session SHALL fail
   the innermost `send_request` with `CompletionTimeout` rather than deadlock indefinitely, and
   the error message SHALL state that the dispatch pool was exhausted.
3. THE Session SHALL propagate the call context's deadline into requests made from within a
   callback, so a nested call cannot outlive the outer call.
4. THE Session SHALL provide `current_call_context()` returning the call context for the
   executing dispatch worker, or `None` on other threads.

### Requirement 4: Delivery Modes

**User Story:** As a service author reporting progress, I want to choose between waiting for
the listener and not waiting, so that a slow listener never stalls the operation reporting to
it.

#### Acceptance Criteria

1. THE RemoteProxy SHALL perform acknowledged calls by default, blocking until the reply or
   exception arrives.
2. THE RemoteProxy SHALL provide `rpc_notify(name, *args, **kwargs)` that sends a RequestCall
   as a notification and returns immediately.
3. WHEN a fire-and-forget callback raises on the target side, THE Session SHALL log the
   exception with the target and callable name and SHALL NOT send an exception message.
4. THE package SHALL provide a `oneway` method decorator that marks a method on a by-reference
   type as fire-and-forget, so that calls through a proxy to that method use notification
   delivery automatically.

### Requirement 5: Call Context and Diagnostics

**User Story:** As an automation engineer, I want to know which call a worker is executing and
who asked for it, so that a hung callback can be attributed.

#### Acceptance Criteria

1. THE call context SHALL expose the session, correlation id, caller session id, target
   reference id, callable name, start time and deadline.
2. THE Session `describe` SHALL include, for each busy dispatch worker, the callable name and
   elapsed time of the callback it is executing.
3. WHEN a callback runs longer than `completion_timeout` from the aspects, THE Session SHALL
   log a warning naming the callable and elapsed time, once, without interrupting it.
