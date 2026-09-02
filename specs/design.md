# Code Craft AI Python RPC Package Design Document

## Overview

The `codecraftai-python-rpc` package is an RPC layer for distributed automation. Its design is
driven by two problems that general purpose RPC libraries create for long running automation:
implicit object proxying (it is not obvious from the code which parameters became network
references) and implicit threading (a callback from the far side can land on the thread that is
waiting for a reply and deadlock it). The package addresses both by making passing semantics
explicit at the call site and by giving every connection its own receive, transmit and dispatch
threads.

## Architecture

### Package Layout

```
ccai/rpc
    rpcsocketclient.py      RpcSocketClient entry point
    rpcsocketserver.py      RpcSocketServer entry point
    core/
        protocol.py         framing constants and message classes
        duplexsocketio.py   length-prefixed socket transport
        duplexclientsession.py
        duplexserversession.py
        looperqueue.py      LooperQueue, LooperQueueShutdown
        looper.py           Looper worker thread base class
        looperpool.py       LooperPool growable worker pool
        proxy.py            ByRef, ByValue
        flattenable.py      Flattenable protocol
```

### Design Principles

- **Debuggability over performance**: threads are named, errors are descriptive, and the message
  layout is simple enough to read in a packet capture.
- **Readability over conciseness**: session and pool code is written out with explicit locking
  rather than compressed into helpers.
- **Explicit over implicit**: nothing crosses the wire unless the caller wrapped it.

## Wire Protocol

Every message is framed on the socket as an 8 byte `!Q` size header followed by the body. Every
body begins with the same prefix:

| Offset | Size | Format | Field |
|--------|------|--------|-------|
| 0      | 4    | `!I`   | message type (`MSG_TYPE_REQUEST`, `MSG_TYPE_REPLY`, `MSG_TYPE_EXCEPTION`) |
| 4      | 4    | `!I`   | message code (`REQ_CODE_*` or `REPLY_CODE_*`) |
| 8      | 36   | uuid   | origin identifier of the sender |

Request codes cover the operations a proxy needs: `PING`, `CLOSE`, `GETSERVICE`, `DELATTR`,
`GETATTR`, `SETATTR` and `CALL`. Each has a message class in `protocol.py` deriving from
`MessageBase`, which owns `pack_prefix`. Message specific payload (attribute name, call arguments)
follows the prefix; the payload encoding is not yet implemented.

## Transport

`DuplexSocketIO` wraps a connected socket together with fixed size send and receive buffers.
`transmit_message` writes the size header then the body in `BUFFER_SIZE` chunks;
`receive_message` reads the size header then loops on `recv_into` until the body is complete.
It has no knowledge of message contents.

## Sessions

`DuplexServerSession` and `DuplexClientSession` are symmetric. Each owns:

- a `DuplexSocketIO`
- a receive thread (`rpc-*-recv`) that loops on `receive_message` and pushes each inbound
  packet to the dispatch pool
- a transmit thread (`rpc-*-xmit`) that waits on a semaphore and drains the outbound queue
- a dispatch `LooperPool` whose loopers (`ServerDispatchLooper`, `ClientDispatchLooper`)
  decode the message prefix and route by type and code
- a table of waiter gates keyed by the calling thread's `thread_guid`, used to correlate a reply
  back to the caller blocked in `send_message`

The flow for a request is:

```
caller thread          transmit thread        far side          receive thread      dispatch worker
-------------          ---------------        --------          --------------      ---------------
send_message
  register gate
  queue message ------> transmit_message ---> ... ---> reply --> receive_message --> push_work
  gate.wait()                                                                       route reply
                                                                                    store response
  <---------------------------------------------------------------------------------- gate.set()
  pop response
```

Because callbacks on `ByRef` objects arrive as requests, they are routed by the dispatch worker
and executed there, never on the receive thread and never on the caller's thread.

## Thread Pool Primitives

- `LooperQueue` couples a list, a counting semaphore and an `RLock`. `push_work` appends and
  releases the semaphore; `pop` acquires the semaphore then takes the head of the list.
  `shutdown_and_wait` appends `LooperQueueShutdown` sentinels and rejects further pushes.
- `Looper` is the worker. `start` spins a named thread that pops packets and calls `loop` until it
  pops a `LooperQueueShutdown`. Subclasses override `loop`.
- `LooperPool` owns one `LooperQueue` and a list of loopers. `start_pool` starts `min_loopers`;
  each push that leaves more than `highwater` packets queued starts another looper up to
  `max_loopers`. `shutdown` pushes enough sentinels to wake every looper and joins them.

## Object Passing

`ByRef` wraps an instance and assigns it a `uuid4` reference id. The owning session keeps a table
from reference id to instance; the far side builds a proxy that turns attribute access and calls
into `RequestAttrGet`, `RequestAttrSet`, `RequestAttrDel` and `RequestCall` messages carrying that
id. `ByValue` wraps an instance that implements `Flattenable`; `flatten` produces the value that
is serialized into the message payload. The proxy class, the reference table and the payload
serialization are open work (see `tasks.md`).

## Entry Points

`RpcSocketServer(service_protocol, endpoint)` binds and listens; `serve_forever` accepts each
connection, wraps it in `DuplexSocketIO`, creates a `DuplexServerSession` and starts it.
`RpcSocketClient(service_protocol, endpoint)` connects, starts a `DuplexClientSession`, and
`get_service` issues `RequestGetService` and returns the resulting proxy typed as
`service_protocol`.

## Error Handling

All package errors come from `ccai.errors.exceptions`: `LooperError` for thread pool misuse,
`AbstractMethodError` for unimplemented `loop` and `flatten` methods, and `ProtocolError` is the
intended type for malformed or unknown messages once dispatch is complete.

## Testing Strategy

Tests use `unittest` under `source/tests`. Protocol tests check constants and message
construction. Thread pool tests exercise `LooperQueue` ordering and shutdown behaviour and the
error paths of `Looper` and `LooperPool` without leaving threads running. Session and transport
tests will use socket pairs on localhost once dispatch is complete.
