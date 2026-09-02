.. _01-00-overview:

********
Overview
********

The ``codecraftai-python-rpc`` package provides a remote procedure call (RPC) layer built for
distributed automation.  It differs from general purpose RPC libraries such as ``rpyc`` in two
deliberate ways:

- **Passing semantics are explicit.**  A parameter or return value crosses the wire only when it is
  wrapped as ``ByRef`` (proxied back to the owning process) or ``ByValue`` (flattened and copied).
  Nothing is implicitly pickled and nothing is implicitly turned into a network reference.
- **Callback threading is built in.**  Every connection is owned by a session object that runs a
  dedicated receive thread, a dedicated transmit thread and a ``LooperPool`` of dispatch workers.
  A callback arriving from the far side is dispatched on a worker, so it can never deadlock the
  thread that is blocked waiting on a reply.

The package depends only on ``codecraftai-foundations`` and the Python standard library.

Core pieces (``ccai.rpc``)
==========================

- ``ccai.rpc.core.protocol`` - the 24 byte header, framing helpers and one message class per request,
  reply and exception, all registered by type and code and round-tripped by ``pack`` and ``unpack``.
- ``ccai.rpc.core.transport`` - the ``Transport`` interface, ``DuplexSocketIO`` over a socket, an
  in-process socket-pair transport for tests and a fault-injecting wrapper.
- ``ccai.rpc.core.serialization`` - the tagged, pickle-free codec with a closed by-value type set.
- ``ccai.rpc.core.session`` - ``DuplexClientSession`` and ``DuplexServerSession``, the per-connection
  objects owning the receive, transmit, heartbeat and dispatch threads and correlating replies by
  request id.
- ``ccai.rpc.core.looperqueue.LooperQueue``, ``ccai.rpc.core.looper.Looper`` and
  ``ccai.rpc.core.looperpool.LooperPool`` - the thread pool primitives.  A ``Looper`` subclass
  overrides ``loop`` to process one work packet; a ``LooperPool`` grows the number of loopers
  between ``min_loopers`` and ``max_loopers`` as the queue depth passes ``highwater``.
- ``ccai.rpc.core.proxy`` - ``ByRef`` and ``ByValue``, the owner-side reference table with leases, and
  ``RemoteProxy``; ``ccai.rpc.core.flattenable.Flattenable`` is the protocol a by-value object implements.
- ``ccai.rpc.aspects.AspectsRpc`` - every tunable in one frozen object, with per-proxy views and a
  per-thread scope.
- ``ccai.rpc.rpcsocketserver.RpcSocketServer`` and ``ccai.rpc.rpcsocketclient.RpcSocketClient`` -
  the entry points.  A server is created with the service protocol type it exposes and the endpoint
  it listens on; a client connects to that endpoint and obtains the remote service object.

See :ref:`02-00-getting-started` for usage examples and the design documents under ``specs/`` for the
reasoning behind each mechanism.
