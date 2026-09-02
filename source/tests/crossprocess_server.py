"""
    The server side of the cross-process test. Run as a script: it serves on an ephemeral port, prints
    ``PORT <n>`` on stdout, and exits when a client calls ``shutdown`` or the process is signalled.
"""

import os
import signal
import sys
import threading
import time

from ccai.rpc import AspectsRpc, RpcSocketServer

from crossprocess_support import Point


class ServerOnlyError(Exception):
    """
        Deliberately defined only in the server process.
    """


class CrossProcessService:

    def __init__(self) -> None:
        self.server = None
        return

    def pid(self) -> int:
        return os.getpid()

    def add(self, a: int, b: int) -> int:
        return a + b

    def fail_known(self):
        raise KeyError("known type")

    def fail_custom(self):
        raise ServerOnlyError("only defined over here")

    def move(self, point: Point, dx: int) -> Point:
        return Point(point.x + dx, point.y)

    def call_back(self, listener) -> int:
        return listener.compute(3)

    def notify(self, listener, count: int) -> str:
        for i in range(count):
            listener.on_event.rpc_notify(i)
        return "sent"

    def shutdown(self) -> str:
        threading.Timer(0.2, self.server.stop).start()
        return "stopping"


def main() -> int:
    aspects = AspectsRpc(heartbeat_interval=0.5, inactivity_timeout=10.0, lease_duration=3.0, completion_timeout=10.0, connection_timeout=5.0)
    service = CrossProcessService()
    server = RpcSocketServer(service, ("127.0.0.1", 0), aspects=aspects)
    service.server = server
    server.start()
    signal.signal(signal.SIGTERM, lambda *_: server.stop())
    sys.stdout.write("PORT {}\n".format(server.bound_endpoint[1]))
    sys.stdout.flush()
    while server.is_serving:
        time.sleep(0.05)
    return 0


if __name__ == "__main__":
    sys.exit(main())
