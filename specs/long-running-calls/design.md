# Design Document — Long-Running Calls

## Overview

Long-running support reuses the session's waiter mechanism. An asynchronous call registers a
waiter exactly like a synchronous one; the difference is that a `RemoteFuture` holds the waiter
instead of the calling thread blocking on it. Cancellation and progress are notifications that
travel in the opposite direction and are matched to the call by correlation id.

## Architecture

### Asynchronous Call

```
caller                        session                         far side
------                        -------                         --------
rpc_call_async("flash")
  waiter = register            queue RequestCall  ---------->  handler runs on worker
  return RemoteFuture(waiter)                                    report_progress(0.5)
                              <---- RequestProgress (notify)
  future.add_progress_callback
    <- invoked on dispatch worker
                              <---- ReplyCall                  returns
  future.result() -> value
```

### Cancellation

`RemoteFuture.cancel` sends RequestCancel carrying the call's correlation id. The receiving
session looks up the call context registry, marks it cancelled, and the handler observes it via
`check_cancelled` or `is_cancelled`. The worker then answers CANCELLED regardless of what the
handler returned, so the caller never mistakes partial work for success.

### Deadline as Implicit Cancellation

The call context already knows its deadline from the Aspects feature. `is_cancelled` returns
`True` once the deadline passes, so a service written to check cancellation also honours
abandonment by timeout with no extra work.

### Design Decisions

1. **Futures over the existing waiter** — no new correlation mechanism; the future is a
   different consumer of the same waiter.
2. **Cooperative cancellation only** — Python cannot safely interrupt a thread, and automation
   services usually have natural check points such as poll loops.
3. **Cancel on local timeout** — a synchronous timeout means the caller is gone; telling the
   server is cheap and prevents ghost work.
4. **Progress is a notification** — it must never block the executing side, and lost progress
   is harmless.
5. **Progress does not extend deadlines** — a service that reports progress forever while
   making none should still time out.
6. **Progress callbacks on dispatch workers** — the same thread guarantee as every callback.

## Components and Interfaces

### File Layout

```
source/packages/ccai/rpc/core/futures.py         RemoteFuture, Progress, wait_all, as_completed
source/packages/ccai/rpc/core/dispatch/cancel.py  cancellation registry, check_cancelled, is_cancelled, report_progress
source/tests/test_futures.py
source/tests/test_cancellation.py
source/tests/test_progress.py
```

### RemoteFuture

```python
class RemoteFuture(Generic[T]):
    correlation_id: uuid.UUID
    callable_name: str
    started_at: datetime
    deadline: Optional[datetime]
    last_progress: Optional[Progress]
    def result(self, timeout: Optional[float] = None) -> T
    def exception(self, timeout: Optional[float] = None) -> Optional[BaseException]
    def wait(self, timeout: Optional[float] = None) -> bool
    def done(self) -> bool
    def cancelled(self) -> bool
    def cancel(self) -> bool
    def add_done_callback(self, fn: Callable[["RemoteFuture[T]"], None]) -> None
    def add_progress_callback(self, fn: Callable[[Progress], None]) -> None
```

### Service-Side Helpers

```python
def is_cancelled() -> bool
def check_cancelled() -> None                     # raises CancelledError
def report_progress(fraction: float, message: Optional[str] = None, **details) -> None
```

## Testing Strategy

Future tests call a service method that sleeps briefly and assert the caller returns
immediately, `result` yields the value, `done` transitions, done callbacks fire, and session
close fails outstanding futures. Cancellation tests use a service loop that calls
`check_cancelled`, cancel from the client, and assert CANCELLED arrives and the loop stopped;
a timeout test asserts RequestCancel was sent. Progress tests assert callbacks receive
increasing fractions on a dispatch thread, `last_progress` updates, and calling
`report_progress` outside a call raises.
