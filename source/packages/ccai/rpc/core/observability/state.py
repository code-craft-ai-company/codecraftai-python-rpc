"""
.. module:: state
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: dump_state renders every live server and client, and can be bound to a signal.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

import json
import logging
import signal

logger = logging.getLogger("ccai.rpc.state")


def live_servers():
    from ccai.rpc.rpcsocketserver import _live_servers
    return list(_live_servers)


def live_clients():
    from ccai.rpc.rpcsocketclient import _live_clients
    return list(_live_clients)


def dump_state() -> str:
    def render(value, indent=0):
        pad = "  " * indent
        if isinstance(value, dict):
            return "\n".join("{}{}:{}".format(pad, key, ("\n" + render(item, indent + 1)) if isinstance(item, (dict, list)) and item else " " + json.dumps(item, default=str))
                             for key, item in value.items())
        if isinstance(value, list):
            return "\n".join("{}-{}".format(pad, ("\n" + render(item, indent + 1)) if isinstance(item, (dict, list)) else " " + json.dumps(item, default=str)) for item in value)
        return pad + json.dumps(value, default=str)

    state = {"servers": [s.describe() for s in live_servers()], "clients": [c.describe() for c in live_clients()]}
    return render(state)


def install_dump_on_signal(signum: int = getattr(signal, "SIGUSR1", 0)) -> bool:
    if not signum:
        return False
    try:
        signal.signal(signum, lambda *_: logger.warning("RPC state dump\n%s", dump_state()))
    except (ValueError, OSError, AttributeError):
        return False
    return True
