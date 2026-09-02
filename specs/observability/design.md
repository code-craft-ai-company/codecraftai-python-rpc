# Design Document — Observability

## Overview

Observability is implemented as a logging adapter per session, a small context mechanism that
rides in a header extension, consistent `describe` methods, and a wire-trace logger that is
silent unless enabled. None of it changes behaviour; all of it exists so that the behaviour is
explainable afterwards.

## Architecture

### Logging Adapter

Each session creates a `logging.LoggerAdapter` over `ccai.rpc.<logger_name>` with `session_id`,
`peer_session_id`, `role` and, on the server, the peer context as `extra`. Every component the
session owns logs through it, so the attributes are present without each call site repeating
them.

### Context Propagation

```
client                                            server
------                                            ------
RpcSocketClient(context={"run_id": "r42"})
  RequestHello(context)  ------------------------>  session.peer_context = {"run_id": "r42"}
with rpc_context_scope(test="t7"):
  proxy.call()  -- header extension {"test":"t7"} -> call context.caller_context =
                                                      {"run_id":"r42", "test":"t7"}
```

The header extension is a small encoded dictionary appended after the fixed header when
present, flagged by a bit in the message type byte so old frames stay valid.

### State Dump

A weak registry of live servers and clients feeds `dump_state`, which calls `describe` on each
and renders the nested dictionaries. `install_dump_on_signal` binds it to `SIGUSR1` on POSIX
and is a no-op elsewhere.

### Design Decisions

0. **Wire trace logs the header only** — direction, type, code, correlation id and payload length per frame, never payload bytes, so credentials cannot reach a log.

1. **Adapter, not per-call extras** — attributes are attached once per session and cannot be
   forgotten.
2. **Context in a header extension, not the payload** — the receive thread can log the
   context for a frame it discards, and it works for every message type.
3. **Session context at HELLO, thread context per request** — the run id is stable for the
   connection; the test id changes per call.
4. **`describe` returns plain data** — usable by loggers, tests and the dump renderer without
   knowing the classes.
5. **Wire trace is a separate logger** — enabling it is one line and it never affects normal
   logging volume.
6. **Counters in the session, sink on close** — cheap, and covers the common case of one
   session per test.

## Components and Interfaces

### File Layout

```
source/packages/ccai/rpc/core/observability/__init__.py
source/packages/ccai/rpc/core/observability/logging.py    session_logger, wire_trace
source/packages/ccai/rpc/core/observability/context.py    rpc_context_scope, header extension codec
source/packages/ccai/rpc/core/observability/state.py      registry, dump_state, install_dump_on_signal
source/packages/ccai/rpc/core/observability/metrics.py    SessionCounters, register_metrics_sink
source/tests/test_observability_logging.py
source/tests/test_observability_context.py
source/tests/test_observability_state.py
```

### Interfaces

```python
def session_logger(role: str, session_id: uuid.UUID, peer_id: Optional[uuid.UUID], name: Optional[str], extra: dict) -> logging.LoggerAdapter
@contextmanager
def rpc_context_scope(**pairs: str) -> Iterator[None]
def dump_state() -> str
def install_dump_on_signal(signum: int) -> None
def register_metrics_sink(sink: Callable[[uuid.UUID, dict], None]) -> None
```

## Testing Strategy

Logging tests capture records with `assertLogs` and check attributes and the pattern
behaviour. Context tests run in-process sessions and assert the server's call context contains
the client context and the scoped pairs. State tests check thread names, `describe` shape and
that `dump_state` renders a running server and client. Wire-trace tests enable the logger and
assert one record per frame with no credential bytes.
