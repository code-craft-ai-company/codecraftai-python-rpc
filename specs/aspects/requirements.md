# Requirements Document — Aspects

## Introduction

The Aspects feature brings the suite's behaviour-parameter pattern to `codecraftai-python-rpc`.
An aspects object is a frozen bundle of the parameters that change how an operation behaves
rather than what it does: connection retries, call timeouts, heartbeat and lease cadence,
dispatch pool sizing and logging. It is passed by the caller, defaults at the session level,
and can be overridden per call. Because timeouts also matter to the far side, the caller's
deadline travels in the request so the server can abandon work the caller has given up on. The
feature derives from `ccai.aspects.Aspects` in `codecraftai-foundations` and is consumed by
every other feature that has a tunable.

## Glossary

- **AspectsRpc**: The aspects class for this package, deriving from `ccai.aspects.Aspects`.
- **Session default**: The `AspectsRpc` a client or server was constructed with.
- **Per-call override**: An `AspectsRpc` applied to one operation through a proxy view.
- **Proxy view**: A `RemoteProxy` bound to a specific aspects object, obtained with
  `rpc_with_aspects`.
- **Deadline**: The absolute time by which the caller expects a reply, derived from
  `completion_timeout` and sent in the request as a remaining-seconds value.
- **DEFAULT_RPC_ASPECTS**: The module-level frozen instance used when no aspects are given.

## Requirements

### Requirement 1: AspectsRpc

**User Story:** As a caller, I want one object that names every RPC tunable, so that I can
define a few named configurations and reuse them across calls.

#### Acceptance Criteria

1. THE AspectsRpc class SHALL derive from `ccai.aspects.Aspects` and SHALL accept keyword-only
   arguments for `completion_interval`, `completion_timeout`, `connection_timeout`,
   `max_attempts` and `logger_name` as defined by the base class.
2. THE AspectsRpc class SHALL add `heartbeat_interval`, `inactivity_timeout`,
   `lease_duration`, `dispatch_min_workers`, `dispatch_max_workers`, `dispatch_highwater`,
   `logging_pattern` and `retry_logging_interval`.
3. THE AspectsRpc class SHALL be immutable after construction and SHALL raise
   `AttributeError` on assignment.
4. THE AspectsRpc class SHALL validate at construction that every timeout and interval is
   positive, that `dispatch_min_workers` is not greater than `dispatch_max_workers`, and that
   `lease_duration` is at least twice `heartbeat_interval`, raising `SemanticError` otherwise.
5. THE AspectsRpc class SHALL provide `replace(**changes)` returning a new instance with the
   given fields changed.
6. THE package SHALL export `DEFAULT_RPC_ASPECTS` with defaults of 30 seconds connection
   timeout, 600 seconds completion timeout, 1 connect attempt, 10 seconds heartbeat, 60 seconds
   inactivity, 90 seconds lease, 2 to 8 dispatch workers with a high-water mark of 4, and
   failure-only logging.
7. THE AspectsRpc class SHALL implement `Flattenable` and SHALL be registered as a by-value type
   so it can be sent over the wire.

### Requirement 2: Session Defaults

**User Story:** As a client author, I want to set behaviour once when I create the client, so
that every call inherits it.

#### Acceptance Criteria

1. THE RpcSocketClient and RpcSocketServer SHALL accept `aspects: AspectsRpc =
   DEFAULT_RPC_ASPECTS` at construction and SHALL expose it as a read-only `aspects` property.
2. THE Session SHALL take its heartbeat interval, inactivity timeout, dispatch pool sizes and
   logging pattern from its aspects.
3. THE RpcSocketClient `connect` SHALL take `connection_timeout`, `max_attempts` and
   `completion_interval` from its aspects for retrying the connection.
4. THE RemoteProxy SHALL use `completion_timeout` from the session's aspects as the default
   timeout for every request.

### Requirement 3: Per-Call Override

**User Story:** As a caller, I want to change behaviour for one call without touching the
remote method's signature, so that a slow operation can have a long timeout and the rest stay
strict.

#### Acceptance Criteria

1. THE RemoteProxy SHALL provide `rpc_with_aspects(aspects) -> RemoteProxy` returning a view of
   the same reference that uses the given aspects for requests made through it.
2. THE proxy view SHALL compare equal to and hash the same as the original proxy.
3. THE proxy view SHALL NOT be cached in the proxy cache and SHALL NOT send a release when
   collected.
4. THE RpcSocketClient `connect` and `get_service` SHALL accept an optional `aspects` argument
   that overrides the session default for that operation.
5. THE package SHALL provide `rpc_aspects_scope(aspects)` as a context manager that sets a
   thread-local override used by every request made on that thread within the block.

### Requirement 4: Deadline Propagation

**User Story:** As a service author, I want to know how long the caller will wait, so that I
can stop work the caller has abandoned.

#### Acceptance Criteria

1. THE RemoteProxy SHALL include the remaining seconds until the caller's deadline in every
   RequestCall, RequestGetAttr, RequestSetAttr and RequestDelAttr.
2. THE dispatch worker SHALL compute an absolute deadline from the received value on its own
   clock and SHALL expose it in the call context.
3. WHEN a callback's deadline has passed before it starts, THE dispatch worker SHALL send an
   ExceptionMessage with code CANCELLED and SHALL NOT invoke the handler.
4. THE package SHALL provide `remaining_time()` returning seconds until the current call
   context's deadline, or `None` outside a call, so service code can check it in loops.
