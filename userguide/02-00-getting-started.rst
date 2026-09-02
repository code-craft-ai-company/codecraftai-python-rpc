.. _02-00-getting-started:

***************
Getting Started
***************

Installation
============

``codecraftai-python-rpc`` is consumed from the Code Craft AI package repository.  For local development
from a checkout:

.. code-block:: bash

    ./repository-setup/rehome-repository
    ./development/setup-environment
    .venv/bin/python-env -m unittest discover -s source/tests -p "test_*.py"

Its only internal dependency is ``codecraftai-foundations``.

Serving and consuming a service
===============================

A server exposes one service object.  A client connects, optionally with retries, and gets a proxy typed
with the service protocol so an IDE and a type checker can see the methods.

.. code-block:: python

    from typing import Protocol

    from ccai.rpc import AspectsRpc, RpcSocketClient, RpcSocketServer

    class Greeter:
        def greet(self, name: str, loud: bool = False) -> str:
            return ("HELLO " if loud else "hello ") + name

    class GreeterProtocol(Protocol):
        def greet(self, name: str, loud: bool = False) -> str: ...

    # server process
    server = RpcSocketServer(Greeter(), ("0.0.0.0", 9040))
    server.start()                      # or server.serve_forever()

    # client process: wait up to a minute for the service to come up
    waiting = AspectsRpc(max_attempts=30, completion_interval=2.0)
    client = RpcSocketClient(GreeterProtocol, ("server-host", 9040), aspects=waiting)
    client.connect()
    greeter = client.get_service()
    greeter.greet("world", loud=True)   # one round trip
    client.close()

A remote exception arrives as the same exception type with the remote traceback attached as
``remote_traceback``; unknown types arrive as ``RemoteError``.

Passing objects
===============

Only a documented set of types crosses the wire by value: ``None``, ``bool``, ``int``, ``float``, ``str``,
``bytes``, ``list``, ``tuple``, ``dict`` with string keys, ``set``, ``frozenset``, aware ``datetime``,
``date``, ``timedelta``, ``UUID``, registered enums and registered ``Flattenable`` types.  Anything else
must say how it travels:

.. code-block:: python

    from ccai.rpc import ByRef, ByValue, by_ref, register_dataclass

    @by_ref                      # every instance is proxied back to its owner
    class Listener:
        def on_event(self, what: str) -> None: ...

    @dataclasses.dataclass
    class Options:
        retries: int = 3
    register_dataclass("myapp.options", Options)     # travels by value

    service.subscribe(Listener())                    # the server gets a proxy
    service.configure(Options(retries=5))            # the server gets a copy
    service.attach(ByRef(some_object))               # explicit at the call site

Passing an unwrapped object that is neither by-value nor by-reference raises ``SerializationError``
before anything is sent, naming the type and the path to it.

Callbacks
=========

A callback on a ``ByRef`` object runs on the holder's dispatch pool, never on the thread that is
waiting for a reply, so a server can call back into a client's listener while the client's own call
is still outstanding.  One-way notifications to the same listener arrive in order; a method marked
``@oneway`` is always delivered that way, and any method can be sent one-way with ``rpc_notify``:

.. code-block:: python

    listener.on_event.rpc_notify("progress")         # returns immediately

Per-call behaviour
==================

Behaviour is controlled by ``AspectsRpc``.  Set it once on the client or server, override it for one
proxy with a view, or for a block of calls with a scope:

.. code-block:: python

    from ccai.rpc import rpc_aspects_scope

    slow = greeter.rpc_with_aspects(AspectsRpc(completion_timeout=1800))
    slow.rebuild_everything()

    with rpc_aspects_scope(AspectsRpc(completion_timeout=5)):
        greeter.greet("quick")

The caller's remaining time travels with each request; service code reads it with ``remaining_time()``
and checks for cancellation with ``check_cancelled()``.

Long operations
===============

.. code-block:: python

    from ccai.rpc import as_completed

    future = greeter.rpc_call_async("provision", host="lab-7")
    future.add_progress_callback(lambda p: print(p.fraction, p.message))
    result = future.result(timeout=1800)             # or future.cancel()

On the service side, ``report_progress(fraction, message)`` sends progress to the caller.

Security
========

.. code-block:: python

    from ccai.rpc.security import shared_secret_authenticator, tls_client_upgrader, tls_server_upgrader

    server = RpcSocketServer(Greeter(), ("0.0.0.0", 9040), authenticator=shared_secret_authenticator(b"secret"),
                             upgrader=tls_server_upgrader(server_ssl_context))
    client = RpcSocketClient(GreeterProtocol, ("host", 9040), credential=b"secret",
                             upgrader=tls_client_upgrader(client_ssl_context, "host"))

Remote access to underscore-prefixed attributes is refused unless the type is decorated with
``@expose_private``; writes to the root service object are refused unless it is ``@mutable_service``.

Diagnostics
===========

Every thread is named ``rpc-<role>-<purpose>-<session>``.  ``client.session.describe()`` and
``server.describe()`` return plain dictionaries, ``ccai.rpc.core.observability.dump_state()`` renders
every live server and client, and enabling the ``ccai.rpc.wire`` logger at debug level traces every
frame's header.
