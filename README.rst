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

This package is early, in-progress work.  The threading primitives and the protocol vocabulary are in
place, but the request dispatch, object proxying and serialization paths are not yet complete.  See
``specs/tasks.md`` for what is done and what remains.

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
