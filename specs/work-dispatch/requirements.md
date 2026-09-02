# Requirements Document — Work Dispatch

## Introduction

The Work Dispatch feature provides the thread pool primitives that every session in
`codecraftai-python-rpc` uses to execute inbound requests and callbacks off the socket threads.
It consists of a thread-safe work queue, a worker thread base class, and a pool that grows and
shrinks the number of workers with demand. The primitives are deliberately small and explicit,
with named threads and descriptive errors, because they sit underneath every callback that the
package promises will never run on a receive thread. The feature is the foundation for Sessions
and Callback Dispatch and has no dependency on any other feature.

## Glossary

- **Work packet**: Any object pushed to a queue for a worker to process. Sessions push a
  packet that pairs the session with the received message bytes.
- **LooperQueue**: A thread-safe queue that couples a list, a counting semaphore signalling
  available packets, and a re-entrant lock protecting the list.
- **LooperQueueShutdown**: A sentinel packet. A worker that pops one exits its loop.
- **Looper**: A worker that owns one thread and repeatedly pops a packet and calls `loop`.
- **LooperPool**: An owner of one `LooperQueue` and a list of `Looper` instances that starts
  `min_loopers` workers and adds workers up to `max_loopers` as demand rises.
- **High-water mark**: The queue depth above which the pool starts an additional worker.
- **LooperError**: The `codecraftai-errors` exception raised for misuse of these primitives.
- **AbstractMethodError**: The `codecraftai-errors` exception raised when `Looper.loop` is not
  overridden.

## Requirements

### Requirement 1: Looper Queue

**User Story:** As a session author, I want a thread-safe work queue that can be shared between
a producer thread and many worker threads, so that inbound messages can be handed off without the
producer knowing which worker will process them.

#### Acceptance Criteria

1. THE LooperQueue SHALL provide a `push_work` method that appends one packet, signals one
   available packet, and returns the resulting queue depth.
2. THE LooperQueue SHALL provide a `push_work_packets` method that appends every packet in a
   list, signals one available packet per appended packet, and returns the resulting queue depth.
3. THE LooperQueue SHALL provide a `pop` method that blocks until a packet is available and
   returns packets in first-in, first-out order.
4. THE LooperQueue SHALL provide a `pop` method that accepts an optional timeout and returns
   `None` when no packet becomes available within the timeout.
5. WHEN `push_work` or `push_work_packets` is called after shutdown has begun, THE LooperQueue
   SHALL raise `LooperError` with a message stating that the queue is shut down.
6. THE LooperQueue SHALL provide a `shutdown` method that accepts a worker count, appends that
   many `LooperQueueShutdown` sentinels, signals one available packet per sentinel, and marks the
   queue as shut down.
7. THE LooperQueue SHALL provide a read-only `depth` property returning the number of packets
   currently queued.

### Requirement 2: Looper

**User Story:** As a session author, I want a worker thread base class where I only implement
the per-packet work, so that thread creation, naming, startup synchronisation and exit
signalling are handled consistently.

#### Acceptance Criteria

1. THE Looper SHALL accept a `LooperQueue`, an optional thread name, an optional group name and
   an optional daemon flag at construction time.
2. WHEN `loop` is called on the base class, THE Looper SHALL raise `AbstractMethodError`.
3. THE Looper SHALL provide a `start` method that creates a named thread, starts it, and returns
   only after the thread has entered its work loop.
4. WHEN a `Looper` pops a `LooperQueueShutdown` sentinel, THE Looper SHALL exit its work loop.
5. WHEN a `Looper` exits its work loop for any reason, THE Looper SHALL set its exit gate so
   that `wait_for_exit` returns.
6. WHEN `loop` raises an exception, THE Looper SHALL log the exception with the packet
   description and continue to the next packet rather than exiting the thread.
7. THE Looper SHALL provide a `wait_for_exit` method that accepts an optional timeout and returns
   `True` when the thread has exited and `False` on timeout.
8. WHEN `wait_for_exit` is called before `start`, THE Looper SHALL raise `LooperError`.
9. THE Looper SHALL provide a `stop` method that requests exit and returns without waiting.
10. THE Looper SHALL provide read-only `name`, `group` and `is_running` properties.

### Requirement 3: Looper Pool

**User Story:** As a session author, I want a pool that manages worker threads for me, so that
a burst of inbound callbacks can be served concurrently without hand-managing threads.

#### Acceptance Criteria

1. THE LooperPool SHALL accept a `Looper` subclass, a group name, `min_loopers`, `max_loopers`,
   a high-water mark, a daemon flag and keyword arguments forwarded to each `Looper`.
2. WHEN `min_loopers` is greater than `max_loopers` or either is less than one, THE LooperPool
   SHALL raise `LooperError` at construction time.
3. THE LooperPool SHALL provide a `start_pool` method that starts `min_loopers` workers named
   `<group>-<n>` and returns after all of them have entered their work loops.
4. WHEN `start_pool` is called on a running pool, THE LooperPool SHALL raise `LooperError`.
5. WHEN `push_work` or `push_work_packets` leaves more than the high-water mark of packets
   queued and fewer than `max_loopers` workers exist, THE LooperPool SHALL start one additional
   worker.
6. WHEN `push_work` or `push_work_packets` is called before `start_pool` or after `shutdown`,
   THE LooperPool SHALL raise `LooperError`.
7. THE LooperPool SHALL provide a `shutdown` method that refuses further work, shuts the queue
   down with one sentinel per worker, waits for every worker to exit within an optional timeout,
   and returns the list of workers that failed to exit.
8. THE LooperPool SHALL provide read-only `worker_count`, `queue_depth` and `is_running`
   properties.

### Requirement 4: Thread Safety and Diagnostics

**User Story:** As an automation engineer debugging a hung run, I want the dispatch threads to
be identifiable and the pool state to be inspectable, so that a thread dump tells me what the
RPC layer was doing.

#### Acceptance Criteria

1. THE LooperPool SHALL protect its worker list and worker count with a lock so that concurrent
   `push_work` calls cannot start more than `max_loopers` workers.
2. THE Looper SHALL name its thread with the name given at construction, and the LooperPool SHALL
   name workers with the group name and an incrementing index.
3. THE LooperPool SHALL provide a `describe` method returning a dictionary with the group name,
   worker count, queue depth, running flag and each worker's name and running state.
