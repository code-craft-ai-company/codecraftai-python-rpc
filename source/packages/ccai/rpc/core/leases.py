"""
.. module:: leases
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The lease-aware protocol an owned object implements to learn that its holder disappeared.

    Lease mechanics live where they act: durations in :mod:`ccai.rpc.aspects`, lease state in the reference
    table, renewal on the session heartbeat and the sweep in the heartbeat monitor.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Protocol, runtime_checkable

import uuid


@runtime_checkable
class ILeaseAware(Protocol):
    """
        Implemented by objects that want a callback when a peer holding a reference to them goes away.
    """

    def on_lease_lapsed(self, peer_session_id: uuid.UUID) -> None: ...


__all__ = ["ILeaseAware"]
