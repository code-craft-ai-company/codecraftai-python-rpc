"""
    Shared fixtures for the session-level tests: an in-process client and server session pair around a small
    service, with short timeouts so failures are fast.
"""

import logging
import threading
import time
from typing import Optional

from ccai.rpc.aspects import AspectsRpc
from ccai.rpc.core.proxy.wrappers import by_ref, concurrent_callbacks, oneway
from ccai.rpc.core.session import DuplexClientSession, DuplexServerSession
from ccai.rpc.core.transport import create_socketpair_transports

logging.getLogger("ccai.rpc").setLevel(logging.ERROR)

FAST = AspectsRpc(heartbeat_interval=0.2, inactivity_timeout=3.0, lease_duration=1.0, completion_timeout=3.0,
                  connection_timeout=3.0, completion_interval=0.05, dispatch_min_workers=2, dispatch_max_workers=4, dispatch_highwater=2)


class Service:
    """
        The service object every session test exposes.
    """

    def __init__(self) -> None:
        self.value = 1
        self._secret = "hidden"
        self.listener = None
        self.items = {"a": 1}
        self.calls = []
        self.helper = Helper()
        return

    def echo(self, *args, **kwargs):
        return (args, kwargs)

    def add(self, a: int, b: int = 0) -> int:
        return a + b

    def fail(self, message: str = "boom"):
        raise KeyError(message)

    def sleep(self, seconds: float) -> str:
        time.sleep(seconds)
        return "slept"

    def register(self, listener) -> None:
        self.listener = listener
        return

    def fire(self, count: int):
        return [self.listener.on_event(i) for i in range(count)]

    def fire_notify(self, count: int) -> None:
        for i in range(count):
            self.listener.on_event.rpc_notify(i)
        return

    def call_back_then_query(self, listener):
        return listener.ask(self)

    def get_helper(self):
        return self.helper

    def new_helper(self):
        return Helper()

    def get_items(self):
        return self.items

    def echo_object(self, obj):
        return obj

    def same(self, obj) -> bool:
        return obj is self

    def slow_loop(self, steps: int, step_seconds: float):
        from ccai.rpc.core.dispatch.context import check_cancelled, report_progress
        for step in range(steps):
            check_cancelled()
            report_progress((step + 1) / steps, "step {}".format(step + 1), step=step + 1)
            time.sleep(step_seconds)
        return "finished"

    def remaining(self):
        from ccai.rpc.aspects import remaining_time
        return remaining_time()

    def caller_context(self):
        from ccai.rpc.core.dispatch.context import current_call_context
        return dict(current_call_context().caller_context)


class Helper:

    def __init__(self) -> None:
        self.data = [1, 2, 3]
        return

    def double(self, x):
        return x * 2

    def __len__(self):
        return len(self.data)

    def __iter__(self):
        return iter(self.data)

    def __contains__(self, item):
        return item in self.data

    def __getitem__(self, index):
        return self.data[index]

    def __setitem__(self, index, value):
        self.data[index] = value
        return

    def __delitem__(self, index):
        del self.data[index]
        return

    def __enter__(self):
        self.entered = True
        return self

    def __exit__(self, *args):
        self.exited = True
        return False


@by_ref
class Listener:

    def __init__(self) -> None:
        self.events = []
        self.lock = threading.Lock()
        self.threads = set()
        return

    def on_event(self, i):
        with self.lock:
            self.events.append(i)
            self.threads.add(threading.current_thread().name)
        return i * 2

    def ask(self, service):
        return service.add(20, 22)

    def on_lease_lapsed(self, peer) -> None:
        self.events.append(("lapsed", peer))
        return


@concurrent_callbacks
@by_ref
class ConcurrentListener(Listener):
    pass


class SessionPair:

    def __init__(self, aspects: AspectsRpc = FAST, service: Optional[object] = None, authenticator=None, credential: bytes = b"",
                 context=None, server_aspects: Optional[AspectsRpc] = None) -> None:
        self.aspects = aspects
        self.service = service if service is not None else Service()
        self.client_transport, self.server_transport = create_socketpair_transports(receive_timeout=0.2)
        self.server = DuplexServerSession(self.server_transport, aspects=server_aspects or aspects, service=self.service, authenticator=authenticator)
        self.client = DuplexClientSession(self.client_transport, aspects=aspects, credential=credential, context=context)
        return

    def start(self) -> "SessionPair":
        self.server.start()
        self.client.start()
        return self

    def proxy(self, protocol=None):
        return self.client.get_service(protocol=protocol)

    def close(self) -> None:
        for session in (self.client, self.server):
            try:
                session.close(timeout=2)
            except Exception:  # noqa: BLE001
                pass
        for transport in (self.client_transport, self.server_transport):
            transport.close()
        return

    def __enter__(self) -> "SessionPair":
        return self.start()

    def __exit__(self, *args) -> None:
        self.close()
        return None
