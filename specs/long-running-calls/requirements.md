# Requirements Document — Long-Running Calls

## Introduction

The Long-Running Calls feature supports operations that take minutes, which are routine in
automation: provisioning a host, flashing firmware, waiting for a cluster. It adds
asynchronous calls that return a future so a caller does not block a thread for the duration,
cooperative cancellation so an abandoned operation can stop, and progress reporting so the
caller can observe partial completion. It depends on Sessions, Callback Dispatch and Aspects.

## Glossary

- **Asynchronous call**: A call issued with `rpc_call_async` that returns immediately with a
  `RemoteFuture`.
- **RemoteFuture**: A future-like object whose result, exception, cancellation and progress
  are driven by session messages.
- **Cancellation**: A RequestCancel naming the correlation id of an outstanding call.
- **Cooperative**: The service checks for cancellation; the runtime never interrupts a thread.
- **Progress**: A RequestProgress notification from the executing side carrying a fraction and a
  message, correlated to the call.

## Requirements

### Requirement 1: Asynchronous Calls

**User Story:** As a caller, I want to start a long operation and do other work, so that I am
not holding a thread for twenty minutes.

#### Acceptance Criteria

1. THE RemoteProxy SHALL provide `rpc_call_async(name, *args, **kwargs) -> RemoteFuture` that
   sends RequestCall and returns without waiting.
2. THE RemoteFuture SHALL provide `result(timeout=None)`, `exception(timeout=None)`, `done()`,
   `cancelled()`, `add_done_callback(fn)` and `wait(timeout=None) -> bool` with the semantics
   of `concurrent.futures.Future`.
3. WHEN the reply arrives, THE RemoteFuture SHALL be completed with the decoded result, and
   WHEN an exception message arrives, with the decoded exception.
4. THE RemoteFuture SHALL expose `correlation_id`, `callable_name`, `started_at` and
   `deadline`.
5. WHEN the session closes with the future outstanding, THE RemoteFuture SHALL be completed
   with `SessionClosedError`.
6. THE package SHALL provide `wait_all(futures, timeout=None)` and `as_completed(futures,
   timeout=None)` helpers.

### Requirement 2: Cancellation

**User Story:** As a caller that has given up, I want to tell the service to stop, so that the
far side does not keep working on my behalf.

#### Acceptance Criteria

1. THE RemoteFuture SHALL provide `cancel()` that sends RequestCancel as a notification and
   returns `True` if the future was not yet done.
2. THE dispatch worker SHALL record the cancellation against the call context so that
   `is_cancelled()` returns `True` inside the executing handler.
3. THE package SHALL provide `check_cancelled()` that raises `CancelledError` inside a handler
   whose call has been cancelled, for service code to call in loops.
4. WHEN a cancelled handler returns or raises, THE dispatch worker SHALL send an
   ExceptionMessage with code CANCELLED rather than the result.
5. WHEN a synchronous call times out locally, THE RemoteProxy SHALL send RequestCancel for it
   before raising `CompletionTimeout`.
6. WHEN a call's deadline passes on the executing side, THE call context SHALL report cancelled
   as though RequestCancel had arrived.

### Requirement 3: Progress

**User Story:** As a caller waiting on a long operation, I want progress, so that I can
distinguish slow from stuck and report it upward.

#### Acceptance Criteria

1. THE package SHALL provide `report_progress(fraction, message=None, **details)` callable from
   inside a handler that sends RequestProgress as a notification correlated to the current
   call.
2. THE RemoteFuture SHALL provide `add_progress_callback(fn)` invoked on a dispatch worker with a
   `Progress` value for each report.
3. THE Progress value SHALL carry the fraction, message, details, correlation id and receipt
   time.
4. THE RemoteFuture SHALL expose `last_progress` returning the most recent Progress or `None`.
5. THE Session SHALL treat a received RequestProgress as liveness for the inactivity timeout but
   SHALL NOT reset the call's deadline.
6. WHEN `report_progress` is called outside a call context, THE package SHALL raise
   `SemanticError`.
