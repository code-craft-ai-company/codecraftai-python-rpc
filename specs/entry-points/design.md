# Design Document — Entry Points

## Overview

`RpcSocketServer` and `RpcSocketClient` are thin owners of sessions. The server owns a listening
socket, an accept thread and a table of server sessions; the client owns one client session.
Both take an `AspectsRpc` and forward it to their sessions. All behaviour of consequence lives
in the features below; the entry points assemble them.

## Architecture

### Server

```
RpcSocketServer.start()
  bind, listen
  accept thread "rpc-server-accept-<port>"
    loop: sock = accept()
          transport = DuplexSocketIO(sock); upgrader(transport) if given
          session = DuplexServerSession(transport, aspects, service)
          sessions[session.session_id] = session
          session.start()
RpcSocketServer.stop()
  close listening socket (unblocks accept)
  for session in sessions: session.close(timeout)
  join accept thread
```

The accept loop tolerates `OSError` from a closed listening socket as the stop signal and logs
any other accept failure without exiting.

### Client

```
RpcSocketClient.connect()
  for attempt in 1..max_attempts:
      endpoint = provider()
      try: sock = create_connection(endpoint, timeout=connection_timeout)
      except OSError as err: last = err; sleep(completion_interval); continue
      transport = DuplexSocketIO(sock); upgrader(transport) if given
      session = DuplexClientSession(transport, aspects); session.start()   # HELLO inside
      return
  raise ConnectionTimeout(endpoint, attempts, last)
```

### Design Decisions

1. **Service instance, not type, on the server** — the current code takes a protocol type and
   has nothing to serve. The instance is the thing exposed; the type belongs to the client for
   typing.
2. **Port zero supported** — tests and parallel runs need ephemeral ports; `bound_endpoint`
   reports the result.
3. **Retry in `connect`** — waiting for a service to come up is the most common client need in
   automation; driving it from aspects keeps it consistent with the rest of the suite.
4. **Stop unblocks accept by closing the socket** — portable and simple; no select loop needed.
5. **Endpoint provider called per attempt** — discovery can move a service between attempts.
6. **Context managers on both** — fits `unittest` fixtures and `with` blocks in scripts.

## Components and Interfaces

### File Layout

```
source/packages/ccai/rpc/__init__.py               re-exports RpcSocketServer, RpcSocketClient, AspectsRpc, ByRef, ByValue, errors
source/packages/ccai/rpc/rpcsocketserver.py         RpcSocketServer
source/packages/ccai/rpc/rpcsocketclient.py         RpcSocketClient
source/packages/ccai/rpc/endpoints.py               IServiceEndpoint, EndpointProvider, ServiceEndpoint
source/tests/test_rpcsocketserver.py
source/tests/test_rpcsocketclient.py
source/tests/test_end_to_end.py
```

### RpcSocketServer

```python
class RpcSocketServer:
    def __init__(self, service: object, endpoint: Tuple[str, int], backlog: int = 16,
                 aspects: AspectsRpc = DEFAULT_RPC_ASPECTS,
                 upgrader: Optional[Callable[[Transport], None]] = None,
                 on_session: Optional[Callable[[DuplexServerSession], None]] = None,
                 on_session_closed: Optional[Callable[[DuplexServerSession, BaseException], None]] = None) -> None
    def start(self) -> None
    def serve_forever(self) -> None
    def stop(self, timeout: Optional[float] = None) -> int
    def advertise(self) -> IServiceEndpoint
    def describe(self) -> dict
    # properties: service, endpoint, bound_endpoint, aspects, is_serving, session_count
```

### RpcSocketClient

```python
class RpcSocketClient(Generic[ServiceProtocol]):
    def __init__(self, service_protocol: Type[ServiceProtocol],
                 endpoint: Union[Tuple[str, int], EndpointProvider],
                 aspects: AspectsRpc = DEFAULT_RPC_ASPECTS,
                 upgrader: Optional[Callable[[Transport], None]] = None) -> None
    def connect(self, aspects: Optional[AspectsRpc] = None) -> None
    def close(self, timeout: Optional[float] = None) -> None
    def get_service(self, aspects: Optional[AspectsRpc] = None) -> ServiceProtocol
    def ping(self, timeout: Optional[float] = None) -> float
    # properties: endpoint, aspects, is_connected, session
```

## Testing Strategy

Server tests bind port zero, assert `bound_endpoint`, start and stop with no clients, and with
several clients, and assert the session table shrinks when a client closes. Client tests
assert `ConnectionTimeout` with the attempt count when nothing listens, that a provider is
called per attempt, and that connecting twice raises. The end-to-end test starts a server with
a small service, connects a client, calls a method, passes a `ByRef` listener, receives a
callback, and stops cleanly. It is the first test that proves the package's purpose and gates
every release.
