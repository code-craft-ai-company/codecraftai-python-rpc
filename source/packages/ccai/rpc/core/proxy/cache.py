"""
.. module:: cache
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The holder-side proxy cache: one proxy per reference id per session, released when collected.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Dict, List

import threading
import uuid
import weakref


class ProxyCache:

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._proxies: Dict[uuid.UUID, "weakref.ReferenceType"] = {}
        return

    def get(self, ref_id: uuid.UUID):
        with self._lock:
            ref = self._proxies.get(ref_id)
            return ref() if ref is not None else None

    def put(self, ref_id: uuid.UUID, proxy) -> None:
        with self._lock:
            self._proxies[ref_id] = weakref.ref(proxy)
        return

    def forget(self, ref_id: uuid.UUID) -> None:
        with self._lock:
            self._proxies.pop(ref_id, None)
        return

    def live_ids(self) -> List[uuid.UUID]:
        with self._lock:
            return [ref_id for ref_id, ref in self._proxies.items() if ref() is not None]

    def live_proxies(self) -> list:
        with self._lock:
            return [ref() for ref in self._proxies.values() if ref() is not None]
