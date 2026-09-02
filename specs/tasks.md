# Code Craft AI Python RPC Package Implementation Tasks

## Task Categories

### 🟢 Completed Tasks
Tasks that are already implemented in the current codebase.

### 🟡 Enhancement Tasks
Tasks to improve existing functionality or add missing features.

### 🔴 Critical Tasks
Tasks that address gaps or issues that must be resolved.

---

## Repository Tasks

### 🟢 TASK-001: Migrate to the codecraftai repository layout
**Status:** Completed
**Description:** Move the package from the `mojo.rpc` namespace to `ccai.rpc`, depend on `codecraftai-errors`, and adopt the shared scaffolding (setup scripts, workflows, user guide, specs, tests)
**Implementation:** `source/packages/ccai/rpc`, `pyproject.toml`, `development/`, `repository-setup/`

## Thread Pool Tasks

### 🟢 TASK-002: Implement LooperQueue
**Status:** Completed
**Requirements:** REQ-009
**Implementation:** `source/packages/ccai/rpc/core/looperqueue.py`
**Validation:** `source/tests/test_looperqueue.py`

### 🟢 TASK-003: Implement Looper base class
**Status:** Completed
**Requirements:** REQ-010
**Implementation:** `source/packages/ccai/rpc/core/looper.py`
**Validation:** `source/tests/test_looper.py`

### 🔴 TASK-004: Fix LooperQueue shutdown wake-up
**Status:** Open
**Requirements:** REQ-009, REQ-010
**Description:** `LooperQueue.shutdown_and_wait` appends `LooperQueueShutdown` sentinels but does not release the availability semaphore, so blocked loopers never wake, and it computes a negative initial value for its wait semaphore whenever more than one packet is queued, which raises `ValueError`. `push_work_packets` releases the semaphore once for the whole list instead of once per packet. `Looper._loop_entry` never sets `_exit_gate`, so `wait_for_exit` always waits for the full timeout.

### 🔴 TASK-005: Fix LooperPool shutdown
**Status:** Open
**Requirements:** REQ-011
**Description:** `LooperPool.shutdown` calls `join` on `Looper` objects, which have no `join`; it should use `wait_for_exit`. It also never sets `_running` back in a way that allows a restart, and the lock is released and re-acquired in the middle of the shutdown sequence.

### 🟡 TASK-006: Cover LooperPool growth and shutdown with tests
**Status:** Open
**Requirements:** REQ-011
**Description:** Once TASK-004 and TASK-005 are done, add tests that start a pool, verify it grows past `highwater`, and verify `shutdown` returns with every looper exited.

## Protocol Tasks

### 🟢 TASK-007: Define message framing and codes
**Status:** Completed
**Requirements:** REQ-001, REQ-002
**Implementation:** `source/packages/ccai/rpc/core/protocol.py`
**Validation:** `source/tests/test_protocol.py`

### 🔴 TASK-008: Make message packing work
**Status:** Open
**Requirements:** REQ-003
**Description:** `FMT_MSG_UUID` is built as 36 separate `s` fields, so `pack_prefix` fails with `struct.error` for every message (verified). Use a `36s` field and encode the origin as bytes. Every `pack` method packs only the prefix; attribute names, attribute values and call arguments are never serialized. There is no exception message class for `MSG_TYPE_EXCEPTION`, and `ReplyPong` is the only reply class, so get-service, attribute and call operations have no way to answer.

### 🔴 TASK-009: Implement message unpacking
**Status:** Open
**Requirements:** REQ-003
**Description:** Add an `unpack` path that reconstructs a message object from bytes so dispatch loopers can route on a typed message instead of raw offsets.

## Transport and Session Tasks

### 🟢 TASK-010: Implement DuplexSocketIO
**Status:** Completed (needs fixes below)
**Requirements:** REQ-004
**Implementation:** `source/packages/ccai/rpc/core/duplexsocketio.py`

### 🔴 TASK-011: Fix DuplexSocketIO send and receive paths
**Status:** Open
**Requirements:** REQ-004
**Description:** `transmit_message` sends slices of the internal (zeroed) send buffer rather than of `msg_bytes`, never advances the slice index, and does not accept the `response_timeout` keyword the sessions pass it. Verified: transmitting `b"hello"` puts five null bytes on the wire. `receive_message` passes the unpack tuple to `BytesIO` and loops on the tuple rather than the integer size, so it raises `TypeError` on any frame, and it reads the 8 byte header with a single `recv` that may return short.

### 🔴 TASK-012: Start session threads
**Status:** Open
**Requirements:** REQ-006
**Description:** `DuplexClientSession.start` and `DuplexServerSession.start` create the receive and transmit threads but never call `start()` on them, then wait on a gate that only the thread sets, so the first call to `start` blocks forever. This also means `RpcSocketServer.serve_forever` hangs on its first accepted connection. Neither session has a `stop` or `close`, and `_running` is never set back to `False`.

### 🔴 TASK-013: Correlate replies to waiting callers
**Status:** Open
**Requirements:** REQ-007
**Description:** The reply path in `ServerDispatchLooper._process_reply` (and the client equivalent) must look up the waiter gate by origin, store the response and set the gate. The request origin must carry the caller's `thread_guid` for this to work.

### 🔴 TASK-014: Align dispatch looper signature with LooperPool
**Status:** Open
**Requirements:** REQ-008
**Description:** `DuplexServerSession._receive_loop` calls `push_work(self, bytes_received)` but `LooperPool.push_work` accepts one packet, and `ServerDispatchLooper.loop(session, packet)` does not match `Looper.loop(packet)`. Package the session and bytes into a single packet, or give the looper the session at construction time. In the same looper, `struct.unpack_from` returns a tuple that is compared to an integer, so every message is reported as an unknown type, and `_process_reply` and `_process_exception` are missing `self`. Both sessions' transmit loops drain the outbound list with `pop()`, which sends messages last-in first-out.

## Object Passing Tasks

### 🟢 TASK-015: Define ByRef, ByValue and Flattenable
**Status:** Completed
**Requirements:** REQ-012, REQ-014
**Implementation:** `source/packages/ccai/rpc/core/proxy.py`, `source/packages/ccai/rpc/core/flattenable.py`
**Validation:** `source/tests/test_proxy.py`

### 🔴 TASK-016: Implement the by-reference proxy class
**Status:** Open
**Requirements:** REQ-013
**Description:** Add a proxy type that forwards `__getattr__`, `__setattr__`, `__delattr__` and `__call__` to the owning session as the corresponding request messages, and a reference table on the owning session keyed by `ByRef` id.

### 🔴 TASK-017: Implement by-value serialization
**Status:** Open
**Requirements:** REQ-014
**Description:** Define how `Flattenable.flatten` output and plain built-in values are encoded into message payloads and decoded on the far side.

## Entry Point Tasks

### 🔴 TASK-018: Complete RpcSocketClient
**Status:** Open
**Requirements:** REQ-016
**Description:** `connect` must open the socket and start a `DuplexClientSession`; `get_service` must send `RequestGetService` and return the resulting proxy.

### 🔴 TASK-019: Complete RpcSocketServer
**Status:** Open
**Requirements:** REQ-015
**Description:** Register the service instance so `REQ_CODE_GETSERVICE` can answer with a reference to it, and add a way to stop `serve_forever`.

### 🟡 TASK-020: End-to-end session tests
**Status:** Open
**Requirements:** REQ-005 through REQ-008
**Description:** Once TASK-008 through TASK-014 are done, add tests that connect a client and server over localhost and exercise ping, get service and a callback on a `ByRef` object.
