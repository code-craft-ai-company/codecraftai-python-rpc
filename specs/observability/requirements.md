# Requirements Document — Observability

## Introduction

The Observability feature makes the RPC layer explain itself. Distributed automation fails in
ways that are only diagnosable after the fact, from logs and thread dumps, so every connection,
request and failure must be attributable to a session and a caller. The feature covers
structured logging, context that travels with requests, thread naming, state description and an
optional wire-level trace. It depends on Sessions and Aspects and touches every other feature.

## Glossary

- **Session id**: The UUID each side assigns at HELLO; the primary key for correlating logs
  across processes.
- **Caller context**: Key-value pairs such as a test run id that a caller attaches to a client
  and that travel in every request header extension.
- **Logging pattern**: The `LoggingPattern` from aspects selecting all results, failures only or
  successes only.
- **Wire trace**: A debug-level dump of every frame's header and payload size, optionally with
  a hex excerpt.
- **Describe**: The `describe()` method each component provides returning a plain dictionary of
  its state.

## Requirements

### Requirement 1: Structured Logging

**User Story:** As an automation engineer, I want RPC events logged with consistent fields, so
that I can filter a run's logs by session and see what the RPC layer did.

#### Acceptance Criteria

1. THE package SHALL log under the `ccai.rpc` logger hierarchy, using the `logger_name` from
   aspects as a child when given.
2. THE Session SHALL log at info level: connect with endpoint and session ids, HELLO outcome
   with version, close with reason, and teardown with cause.
3. THE dispatch worker SHALL log each request outcome according to the logging pattern, with
   the request code, target type, callable name, caller session id, duration and outcome.
4. THE Session SHALL log at warning level: discarded frames, stray replies, lease expiries,
   inactivity teardown, pool saturation and long-running callbacks.
5. THE Session SHALL log at error level any exception in a receive, transmit, heartbeat or
   accept thread, with the traceback.
6. EVERY log record SHALL carry `session_id`, `peer_session_id` and `role` as record attributes
   so formatters can include them.

### Requirement 2: Caller Context

**User Story:** As a test framework author, I want my run id to appear in the service's logs,
so that server-side failures can be tied to the test that caused them.

#### Acceptance Criteria

1. THE RpcSocketClient SHALL accept a `context: Dict[str, str]` at construction and SHALL send
   it in RequestHello.
2. THE server Session SHALL attach the received context to every log record it emits for that
   session and expose it as `peer_context`.
3. THE package SHALL provide `rpc_context_scope(**pairs)` as a context manager that adds pairs
   to every request sent on the thread within the block, delivered in the request header
   extension and visible in the call context on the far side.
4. THE call context SHALL expose `caller_context` merging the session context and the request
   context.

### Requirement 3: Thread Naming and State

**User Story:** As an engineer with a thread dump of a hung process, I want thread names and a
state dump that tell me what the RPC layer was doing.

#### Acceptance Criteria

1. THE package SHALL name every thread it creates with the `rpc-` prefix, the role, the purpose
   and a short session id as specified in Sessions.
2. THE RpcSocketServer, RpcSocketClient, Session, LooperPool and ReferenceTable SHALL each
   provide `describe()` returning a dictionary of plain values.
3. THE package SHALL provide `dump_state() -> str` that renders every live server and client's
   description as indented text, suitable for a signal handler or a test failure hook.
4. THE package SHALL provide `install_dump_on_signal(signum)` that registers `dump_state`
   output to the log on the given signal on platforms that support it.

### Requirement 4: Wire Trace

**User Story:** As a protocol implementer, I want to see frames, so that a framing or encoding
bug can be found without a packet capture.

#### Acceptance Criteria

1. WHEN the `ccai.rpc.wire` logger is enabled at debug level, THE Session SHALL log every sent
   and received frame's direction, header fields and payload length.
2. THE wire trace SHALL include a hex excerpt of up to a configurable number of payload bytes.
3. THE wire trace SHALL NOT log credential bytes from RequestHello.

### Requirement 5: Metrics Hooks

**User Story:** As an operator, I want counters, so that a dashboard can show RPC health without
parsing logs.

#### Acceptance Criteria

1. THE Session SHALL maintain counters for requests sent, requests received, replies, exceptions,
   timeouts, bytes sent and bytes received, exposed in `describe`.
2. THE package SHALL provide `register_metrics_sink(callable)` invoked with the counter
   dictionary and session id on session close, so an external system can collect them.
