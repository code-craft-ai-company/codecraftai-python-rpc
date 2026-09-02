# Design Document — Callback Dispatch

## Overview

Callback Dispatch is a set of rules layered on the session's dispatch pool rather than a new
component. The pool already guarantees callbacks never run on the socket threads. This feature
adds per-target ordering, a call context, re-entrancy behaviour, delivery modes and the
diagnostics that make callback problems visible.

## Architecture

### Per-Target Ordering

```
receive thread                      dispatch worker
--------------                      ---------------
frame (REQUEST, CALL, ref A)        
  pool.push_work((session, frame))  pop -> unpack -> target A
                                    lane = lanes.get_or_create(A)
                                    lane.run(handler)         # serialises per target
```

A `TargetLane` holds a lock and a small FIFO. A worker that finds the lane busy appends its
work to the lane's FIFO and returns to the pool; the worker that holds the lane drains the FIFO
before releasing it. Workers are therefore never blocked waiting on a lane, and ordering per
target is preserved without dedicating a thread per target. Types decorated with
`concurrent_callbacks` bypass the lane.

### Call Context

A thread-local `CallContext` is set by the dispatch worker before invoking the handler and
cleared after. `send_request` reads it to inherit the deadline. `describe` reads every
worker's current context to report busy callbacks.

### Re-entrancy

Nothing special is needed for the common case: a callback on worker W calls `send_request`,
W blocks, other workers keep serving. The failure case is exhaustion: both sides have every
worker blocked in a nested call. The deadline inherited from the outer call bounds the wait,
and the timeout message includes the pool description so exhaustion is recognisable.

### Delivery Modes

Acknowledged calls use `send_request`. `rpc_notify` and `@oneway` methods use
`send_notification` with a RequestCall whose correlation id the receiver does not answer. The
receiving handler checks a flag on the message and suppresses the reply.

### Design Decisions

0. **Lanes apply to one-way callbacks only** — an acknowledged call already serialises its caller, and a lane on an acknowledged call deadlocks a re-entrant chain that targets the same object (the nested call queues behind the outer call that is waiting for it). Notification bursts to one target stay ordered; acknowledged calls run on any free worker.

1. **Lanes, not per-object threads** — ordering per target without unbounded thread creation
   and without blocking pool workers.
2. **Ordered by default** — listeners almost always assume ordered events; opting out is
   explicit through the class decorator.
3. **Deadline inheritance** — nested calls that outlive their parent are a source of ghost work
   in long runs; the context makes the bound automatic.
4. **Exhaustion produces a timeout with a diagnosis** — a real deadlock detector across two
   processes is out of scope; a bounded wait with a clear message is the practical answer.
5. **`@oneway` on the type** — progress and log-style callbacks are one-way by nature, and the
   author of the listener type knows that better than each caller.

## Components and Interfaces

### File Layout

```
source/packages/ccai/rpc/core/dispatch/__init__.py
source/packages/ccai/rpc/core/dispatch/lanes.py        TargetLane, LaneTable
source/packages/ccai/rpc/core/dispatch/context.py      CallContext, current_call_context
source/packages/ccai/rpc/core/dispatch/decorators.py   concurrent_callbacks, oneway
source/tests/test_dispatch_ordering.py
source/tests/test_dispatch_reentrancy.py
source/tests/test_dispatch_delivery.py
```

### CallContext

```python
@dataclass(frozen=True)
class CallContext:
    session: DuplexSessionBase
    correlation_id: uuid.UUID
    caller_session_id: uuid.UUID
    target_ref: uuid.UUID
    callable_name: str
    started_at: datetime
    deadline: Optional[datetime]

def current_call_context() -> Optional[CallContext]
```

### Decorators

```python
def concurrent_callbacks(cls: type) -> type
def oneway(method: Callable) -> Callable
```

Both set a marker attribute that the proxy layer and the dispatch handler consult.

## Testing Strategy

Ordering tests send a burst of callbacks to one listener from a server-side thread and assert
arrival order, then repeat with two listeners and assert interleaving occurred. A thread-name
test asserts every callback ran on a `dispatch` thread. Re-entrancy tests have a listener call
the service from inside its callback and assert the outer call completes, then exhaust a pool
of size one on both sides and assert the specific timeout message. Delivery tests assert
`rpc_notify` returns before the listener runs, that a raising one-way callback is logged and not
propagated, and that `@oneway` methods use notification delivery.
