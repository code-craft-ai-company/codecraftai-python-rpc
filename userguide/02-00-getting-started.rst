.. _02-00-getting-started:

***************
Getting Started
***************

Installation
============

``codecraftai-python-rpc`` is consumed by other ``codecraftai-*`` packages from the Code Craft AI
package repository.  For local development from a checkout:

.. code-block:: bash

    ./repository-setup/rehome-repository
    ./development/setup-environment

Its only runtime dependency is ``codecraftai-errors``.  Once the virtual environment is set up the
package imports directly through the ``python-env`` wrapper:

.. code-block:: bash

    .venv/bin/python-env -c "import ccai.rpc"

Running the tests
=================

.. code-block:: bash

    .venv/bin/python-env -m unittest discover -s source/tests -p "test_*.py"

Processing work with a ``Looper`` and ``LooperPool``
====================================================

The thread pool primitives are the most complete part of the package today.  Subclass ``Looper``
and override ``loop`` to process a single work packet:

.. code-block:: python

    from ccai.rpc.core.looper import Looper
    from ccai.rpc.core.looperpool import LooperPool

    class PrintLooper(Looper):

        def loop(self, packet) -> bool:
            print(f"processing {packet}")
            return True

    pool = LooperPool(PrintLooper, group_name="printers", min_loopers=2, max_loopers=4, daemon=True)
    pool.start_pool()

    pool.push_work("first")
    pool.push_work_packets(["second", "third"])

Declaring passing semantics
===========================

Parameters that cross the wire are wrapped so the RPC layer knows how to handle them:

.. code-block:: python

    from ccai.rpc.core.proxy import ByRef, ByValue

    # The remote side receives a proxy; calls on it come back to this process.
    listener = ByRef(my_event_listener)

    # The remote side receives a flattened copy.
    options = ByValue(my_options)

Serving and consuming a service
===============================

The intended shape of the server and client entry points is shown below.  Request dispatch and
object proxying are still being implemented, so this is the API direction rather than a working
end-to-end example.

.. code-block:: python

    from typing import Protocol

    from ccai.rpc.rpcsocketserver import RpcSocketServer
    from ccai.rpc.rpcsocketclient import RpcSocketClient

    class GreeterService(Protocol):
        def greet(self, name: str) -> str: ...

    # Server process
    server = RpcSocketServer(GreeterService, ("0.0.0.0", 9040))
    server.serve_forever()

    # Client process
    client = RpcSocketClient(GreeterService, ("server-host", 9040))
    client.connect()
    greeter = client.get_service()
