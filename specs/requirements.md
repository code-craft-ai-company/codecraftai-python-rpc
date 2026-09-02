# Code Craft AI Python RPC Package Requirements

## 1. Functional Requirements

### 1.1 Wire Protocol

**REQ-001: Message Framing**
- Every message on the wire SHALL be preceded by an 8 byte, network byte order, unsigned size header
- Every message body SHALL begin with a fixed prefix of message type, message code and origin identifier
- Message type and message code SHALL be 4 byte, network byte order, unsigned integers

**REQ-002: Message Types**
- The protocol SHALL distinguish request, reply and exception messages by message type
- Request messages SHALL carry a request code identifying the operation (ping, close, get service, get attribute, set attribute, delete attribute, call)
- Reply messages SHALL carry a reply code and SHALL echo the origin identifier of the request they answer

**REQ-003: Message Classes**
- The system SHALL provide one message class per request and reply code, each with a `pack` method that produces the message bytes
- The system SHALL provide a corresponding unpack path so a session can reconstruct a message from bytes

### 1.2 Transport

**REQ-004: Duplex Socket Transport**
- The system SHALL provide a `DuplexSocketIO` wrapper over a connected socket
- `transmit_message` SHALL send the size header followed by the complete message body
- `receive_message` SHALL read the size header and then read exactly that many bytes, looping on partial reads

### 1.3 Sessions and Threading

**REQ-005: Session per Connection**
- Each accepted connection on the server, and each connection made by a client, SHALL be owned by a session object
- A session SHALL multiplex all RPC traffic for that connection over a single socket

**REQ-006: Dedicated Session Threads**
- A session SHALL run a dedicated receive thread that does nothing but read messages and hand them to a dispatch pool
- A session SHALL run a dedicated transmit thread that drains an outbound queue onto the socket
- Callers SHALL never write to the socket from their own thread

**REQ-007: Reply Correlation**
- A caller that sends a request and waits for a reply SHALL block on a per-call gate
- The receive path SHALL correlate an inbound reply to the waiting caller and release its gate
- A caller SHALL raise a descriptive error if no reply arrives within the response timeout

**REQ-008: Callback Dispatch**
- Inbound requests (including callbacks on `ByRef` objects) SHALL be executed on dispatch pool workers
- A callback SHALL never execute on the receive thread or on the thread that is blocked waiting for a reply

### 1.4 Thread Pool Primitives

**REQ-009: Looper Queue**
- The system SHALL provide a thread-safe `LooperQueue` that couples a work list, an availability semaphore and a lock
- Pushing work after the queue has been shut down SHALL raise `LooperError`
- Popping SHALL block until work is available and SHALL return packets in first-in, first-out order

**REQ-010: Looper**
- The system SHALL provide a `Looper` base class whose `loop` method processes one work packet
- Calling `loop` on the base class SHALL raise `AbstractMethodError`
- A `Looper` SHALL exit its work loop when it pops a `LooperQueueShutdown` packet
- Waiting for exit before the looper is started SHALL raise `LooperError`

**REQ-011: Looper Pool**
- The system SHALL provide a `LooperPool` that starts `min_loopers` workers and grows to at most `max_loopers` as queued work exceeds `highwater`
- Pushing work before the pool is started, or after it is shut down, SHALL raise `LooperError`
- Shutting the pool down SHALL wake every worker and wait for each to exit

### 1.5 Object Passing Semantics

**REQ-012: Explicit Passing Declarations**
- Objects SHALL cross the wire only when wrapped as `ByRef` or `ByValue`
- A `ByRef` wrapper SHALL assign a unique reference identifier to the wrapped instance
- The system SHALL NOT implicitly pickle or implicitly proxy unwrapped objects

**REQ-013: By-Reference Proxies**
- The receiving side SHALL materialize a `ByRef` object as a proxy
- Attribute access, attribute assignment, attribute deletion and calls on a proxy SHALL be forwarded to the owning process as the corresponding request messages

**REQ-014: By-Value Flattening**
- A `ByValue` object SHALL implement the `Flattenable` protocol
- Calling `flatten` on an object that does not implement it SHALL raise `AbstractMethodError`

### 1.6 Entry Points

**REQ-015: Server**
- The system SHALL provide an `RpcSocketServer` that is created with a service protocol type and a listen endpoint
- `serve_forever` SHALL accept connections and start a `DuplexServerSession` for each

**REQ-016: Client**
- The system SHALL provide an `RpcSocketClient` that is created with a service protocol type and a service endpoint
- `connect` SHALL establish the socket and start a `DuplexClientSession`
- `get_service` SHALL return a proxy to the remote service object typed as the service protocol

## 2. Non-Functional Requirements

**REQ-017: Dependencies**
- The package SHALL depend only on `codecraftai-errors` and the Python standard library

**REQ-018: Debuggability**
- Errors raised for protocol violations, missing replies and misuse of the thread pool SHALL carry descriptive messages
- Threads created by the package SHALL be named so they are identifiable in debuggers and thread dumps

**REQ-019: Platform Support**
- The package SHALL run on Linux, macOS and Windows with Python 3.10 or later
