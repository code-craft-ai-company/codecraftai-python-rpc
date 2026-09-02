# Implementation Plan: Work Dispatch

## Overview

Repair and complete the thread pool primitives under `source/packages/ccai/rpc/core/`. The queue
is fixed first because both the worker and the pool depend on its wake-up invariant, then the
worker exit path, then the pool's growth and shutdown. Tests live in `source/tests/`.

## Tasks

- [x] 1. Basic queue, worker and pool
  - [x] 1.1 `LooperQueue` push, FIFO pop and shutdown guard
    - _Requirements: 1.1, 1.3, 1.5_
  - [x] 1.2 `Looper` start with startup gate, sentinel exit, abstract `loop`
    - _Requirements: 2.1, 2.2, 2.3, 2.4, 2.8_
  - [x] 1.3 `LooperPool` start and growth past the high-water mark
    - _Requirements: 3.1, 3.3, 3.5, 3.6_
  - [x] 1.4 Tests for the working paths
    - `test_looperqueue.py`, `test_looper.py`

- [ ] 2. Fix the queue wake-up invariant
  - [ ] 2.1 Release the semaphore once per packet in `push_work_packets`
    - _Requirements: 1.2_
  - [ ] 2.2 Replace `shutdown_and_wait` with `shutdown(worker_count)` that appends and signals one sentinel per worker
    - Remove the negative-value semaphore, which raises `ValueError` whenever more than one packet is queued
    - _Requirements: 1.6_
  - [ ] 2.3 Add the timed `pop` and the `depth` property
    - _Requirements: 1.4, 1.7_
  - [ ] 2.4 Tests: one wake-up per packet, timed pop returns `None`, shutdown signals every waiter
    - _Requirements: 1.2, 1.4, 1.6_

- [ ] 3. Fix the worker exit path
  - [ ] 3.1 Set the exit gate in a `finally` block in `_loop_entry`
    - _Requirements: 2.5_
  - [ ] 3.2 Catch and log exceptions from `loop`, continue to the next packet
    - _Requirements: 2.6_
  - [ ] 3.3 Make `wait_for_exit` return a boolean; add `stop`, `name`, `group`, `is_running`
    - _Requirements: 2.7, 2.9, 2.10_
  - [ ] 3.4 Tests: exit gate set after sentinel, raising `loop` keeps the thread alive, `stop` then sentinel exits
    - _Requirements: 2.5, 2.6, 2.7_

- [ ] 4. Fix pool shutdown and validation
  - [ ] 4.1 Validate `min_loopers` and `max_loopers` at construction
    - _Requirements: 3.2_
  - [ ] 4.2 Rewrite `shutdown` to use `queue.shutdown` and `wait_for_exit`, returning stragglers
    - The current code calls `join` on `Looper` objects, which have no `join`
    - _Requirements: 3.7_
  - [ ] 4.3 Raise on `start_pool` while running; add `worker_count`, `queue_depth`, `is_running`, `describe`
    - _Requirements: 3.4, 3.8, 4.3_
  - [ ] 4.4 Hold the pool lock across the count check and worker start
    - _Requirements: 4.1_
  - [ ] 4.5 Tests: growth stops at `max_loopers`, `shutdown` returns with all workers exited, `describe` content
    - _Requirements: 3.5, 3.7, 4.3_

- [ ] 5. Checkpoint - Ensure all tests pass
