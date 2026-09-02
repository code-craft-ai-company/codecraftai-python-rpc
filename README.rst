=================================================
Code Craft AI Python RPC - codecraftai-python-rpc
=================================================

The ``codecraftai-python-rpc`` package is a remote procedure call (RPC) layer for the ccai suite that
is designed with distributed automation in mind.  Its two defining goals are:

- **Explicit object passing semantics.**  Objects that cross the wire are wrapped as ``ByRef`` or
  ``ByValue`` so the caller declares, in code, whether a parameter is proxied back to its owner or
  flattened and copied.  Nothing is silently pickled or silently proxied.
- **Callback threading that keeps automation stable.**  Every session multiplexes one socket across
  dedicated receive and transmit threads and hands inbound messages to a ``LooperPool`` of dispatch
  workers, so a callback from the far side never blocks the thread that is waiting on a reply.

The package is an alternative to ``rpyc`` style libraries for cases where the implicit threading
and implicit netref behaviour of those libraries makes long running automation hard to reason about.

Highlights
==========

- ``ccai.rpc.core.protocol`` - the binary message framing (message type, message code, origin id) and
  the request and reply message classes such as ``RequestPing``, ``RequestCall`` and ``ReplyPong``.
- ``ccai.rpc.core.duplexsocketio`` - length-prefixed message transmit and receive over a socket.
- ``ccai.rpc.core.duplexclientsession`` / ``duplexserversession`` - the per-connection session objects
  that own the receive thread, the transmit thread and the dispatch pool.
- ``ccai.rpc.core.looper``, ``looperqueue`` and ``looperpool`` - the thread pool primitives used to
  dispatch inbound requests and callbacks.
- ``ccai.rpc.core.proxy`` - the ``ByRef`` and ``ByValue`` wrappers that declare passing semantics.
- ``ccai.rpc.rpcsocketclient`` / ``rpcsocketserver`` - the ``RpcSocketClient`` and ``RpcSocketServer``
  entry points that a service and its consumers use.

Status
======

The package is implemented end to end: framing and a pickle-free codec, sessions with correlation,
remote exceptions, heartbeats and leases, typed proxies, ordered one-way callbacks, asynchronous calls
with cancellation and progress, aspects-driven behaviour, TLS and token authentication.  The test suite
under ``source/tests`` exercises the full stack in-process and over TCP.  The design record for each
feature is under ``specs/``.

Quick Start
===========

.. code-block:: python

    from typing import Protocol
    from ccai.rpc import RpcSocketServer, RpcSocketClient, by_ref

    class Greeter:
        def greet(self, name: str) -> str:
            return "hello " + name
        def subscribe(self, listener) -> None:
            listener.on_event("subscribed")      # runs on the client's dispatch pool, never its caller thread

    class GreeterProtocol(Protocol):
        def greet(self, name: str) -> str: ...
        def subscribe(self, listener) -> None: ...

    @by_ref
    class Listener:
        def on_event(self, what: str) -> None:
            print("event:", what)

    with RpcSocketServer(Greeter(), ("127.0.0.1", 0)) as server:
        with RpcSocketClient(GreeterProtocol, server.bound_endpoint) as client:
            greeter = client.get_service()
            print(greeter.greet("world"))
            greeter.subscribe(Listener())

Code Organization
=================

* ``.vscode`` - Common tasks
* ``development`` - This is where the runtime environment scripts are located
* ``prompts`` - Pre-built prompts for agent driven work such as bug bashes
* ``repository-setup`` - Scripts for homing your repository and to your checkout and machine setup
* ``specs`` - Requirements, design and task specifications that steer development
* ``userguide`` - The user guide and the coding standards for the repository
* ``source/packages`` - The ``ccai.rpc`` package source
* ``source/tests`` - The ``unittest`` based tests for the package
* ``workspaces`` - This is where you add VSCode workspaces templates and where workspaces show up when homed.

References
==========

- `User Guide <userguide/userguide.rst>`_
- `Coding Standards <userguide/10-00-coding-standards.rst>`_
