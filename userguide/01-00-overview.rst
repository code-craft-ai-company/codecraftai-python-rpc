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

- ``ccai.rpc.core.protocol`` - message framing constants (``MSG_TYPE_*``, ``REQ_CODE_*``,
  ``REPLY_CODE_*``) and the message classes ``RequestPing``, ``RequestClose``,
  ``RequestGetService``, ``RequestAttrGet``, ``RequestAttrSet``, ``RequestAttrDel``,
  ``RequestCall`` and ``ReplyPong``.  Every message starts with a fixed prefix of message type,
  message code and the origin identifier of the sender.
- ``ccai.rpc.core.duplexsocketio.DuplexSocketIO`` - wraps a connected socket and provides
  length-prefixed ``transmit_message`` and ``receive_message`` operations.
- ``ccai.rpc.core.duplexclientsession.DuplexClientSession`` and
  ``ccai.rpc.core.duplexserversession.DuplexServerSession`` - the per-connection session objects.
  They own the receive thread, the transmit thread and the dispatch pool, and they correlate
  replies back to the waiting caller by thread identity.
- ``ccai.rpc.core.looperqueue.LooperQueue``, ``ccai.rpc.core.looper.Looper`` and
  ``ccai.rpc.core.looperpool.LooperPool`` - the thread pool primitives.  A ``Looper`` subclass
  overrides ``loop`` to process one work packet; a ``LooperPool`` grows the number of loopers
  between ``min_loopers`` and ``max_loopers`` as the queue depth passes ``highwater``.
- ``ccai.rpc.core.proxy.ByRef`` and ``ByValue`` - wrappers that declare passing semantics, and
  ``ccai.rpc.core.flattenable.Flattenable`` - the protocol a by-value object implements.
- ``ccai.rpc.rpcsocketserver.RpcSocketServer`` and ``ccai.rpc.rpcsocketclient.RpcSocketClient`` -
  the entry points.  A server is created with the service protocol type it exposes and the endpoint
  it listens on; a client connects to that endpoint and obtains the remote service object.

See :ref:`02-00-getting-started` for usage examples, and the ``tasks.md`` in each feature folder under ``specs/`` for the current state of
the implementation.
