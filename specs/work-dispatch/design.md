# Design Document — Work Dispatch

## Overview

Work Dispatch is the thread pool layer of `codecraftai-python-rpc`. It provides three classes
in `ccai.rpc.core`:

- `LooperQueue`, a queue that a producer pushes to and workers pop from, with a counting
  semaphore so a worker blocks only while the queue is empty.
- `Looper`, a worker thread whose subclass implements `loop(packet)`.
- `LooperPool`, which owns a queue and a growable set of loopers.

Sessions use a pool for dispatch: the receive thread pushes each inbound message and a pool
worker decodes and executes it. The design keeps the primitives independent of the protocol so
they can be tested with plain Python objects and reused by other packages if needed.

## Architecture

### Queue and Worker Interaction

```
producer                LooperQueue                       Looper thread
--------                -----------                       -------------
push_work(p)  ------>   lock; append; unlock
                        semaphore.release()  -------->    semaphore.acquire()
                                                          lock; pop(0); unlock
                                                          loop(p)
shutdown(n)   ------>   lock; append n sentinels; mark shut down; unlock
                        semaphore.release() x n --------> pops sentinel -> exit loop
                                                          exit_gate.set()
```

The semaphore count always equals the number of packets appended and not yet popped. That
invariant is what makes shutdown reliable: one release per sentinel guarantees one wake-up per
worker.

### Pool Growth

`LooperPool.push_work` pushes to the queue, reads the returned depth, and if the depth exceeds
the high-water mark and the worker count is below the maximum, starts one more looper under the
pool lock. Growth is one worker per push so a burst cannot over-provision. The pool never shrinks
on its own; `shutdown` is the only way workers exit. This matches the sessions' usage, where the
pool lives as long as the connection.

### Shutdown Sequence

1. Set `running` to `False` under the pool lock so new pushes raise.
2. Snapshot the worker list.
3. Call `queue.shutdown(len(workers))`, which appends and signals one sentinel per worker.
4. Call `wait_for_exit(timeout)` on each worker and collect those that did not exit.
5. Return the stragglers so the caller can log them. Daemon workers cannot hold the process open.

### Design Decisions

1. **Semaphore per packet, not per push** — `push_work_packets` releases once per packet.
   The previous single release is the root cause of workers sleeping through shutdown.
2. **Sentinels rather than a stop flag** — a worker blocked in `pop` cannot observe a flag.
   Queued sentinels wake exactly the workers that need waking, in order, after pending work.
3. **`loop` exceptions are logged, not fatal** — a callback that raises must not silently
   kill a dispatch worker; the pool would then starve with no error. The exception is logged with
   the packet's `repr` and the worker continues.
4. **No shrinking** — shrinking requires idle detection and adds races for little benefit in
   sessions that live for the whole connection.
5. **Names everywhere** — every thread is named `<group>-<index>`, and `describe` exposes the
   pool state, because thread dumps are the primary tool for diagnosing hung automation.
6. **Exceptions from `ccai.errors`** — `LooperError` and `AbstractMethodError` are
   reused rather than defining local types.

## Components and Interfaces

### File Layout

```
source/packages/ccai/rpc/core/looperqueue.py     LooperQueue, LooperQueueShutdown
source/packages/ccai/rpc/core/looper.py          Looper
source/packages/ccai/rpc/core/looperpool.py      LooperPool
source/tests/test_looperqueue.py
source/tests/test_looper.py
source/tests/test_looperpool.py
```

### LooperQueue

```python
class LooperQueue:
    def __init__(self) -> None
    @property
    def depth(self) -> int
    @property
    def is_shutdown(self) -> bool
    def push_work(self, packet: object) -> int
    def push_work_packets(self, packets: Sequence[object]) -> int
    def pop(self, timeout: Optional[float] = None) -> Optional[object]
    def shutdown(self, worker_count: int) -> None
```

### Looper

```python
class Looper:
    def __init__(self, queue: LooperQueue, name: Optional[str] = None,
                 group: Optional[str] = None, daemon: Optional[bool] = None, **kwargs) -> None
    @property
    def name(self) -> str
    @property
    def group(self) -> Optional[str]
    @property
    def is_running(self) -> bool
    def loop(self, packet: object) -> None            # raises AbstractMethodError
    def start(self) -> None
    def stop(self) -> None
    def wait_for_exit(self, timeout: Optional[float] = None) -> bool
```

`_loop_entry` wraps the whole loop in `try/finally` so the exit gate is set on every path.

### LooperPool

```python
class LooperPool:
    def __init__(self, looper_type: Type[Looper], group_name: str,
                 min_loopers: int = 2, max_loopers: int = 8, highwater: int = 4,
                 daemon: bool = True, **looper_kwargs) -> None
    @property
    def is_running(self) -> bool
    @property
    def worker_count(self) -> int
    @property
    def queue_depth(self) -> int
    def start_pool(self) -> None
    def push_work(self, packet: object) -> int
    def push_work_packets(self, packets: Sequence[object]) -> int
    def shutdown(self, timeout: Optional[float] = None) -> List[Looper]
    def describe(self) -> dict
```

## Testing Strategy

Tests use `unittest` and small timeouts. Queue tests cover ordering, depth reporting, one
wake-up per packet, timed-out pop, and the shutdown guard. Looper tests use a recording subclass
and assert that `start` returns after the loop is entered, that a sentinel exits the loop and
sets the exit gate, and that a raising `loop` does not kill the thread. Pool tests assert
growth past the high-water mark, the maximum, and that `shutdown` returns with every worker
exited. Every test that starts threads shuts them down in `tearDown`.
