"""
.. module:: metrics
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Package-level metrics sinks invoked with a session's counters when it closes.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Callable, List

import uuid

_sinks: List[Callable[[uuid.UUID, dict], None]] = []


def register_metrics_sink(sink: Callable[[uuid.UUID, dict], None]) -> None:
    _sinks.append(sink)
    return


def metrics_sinks() -> List[Callable[[uuid.UUID, dict], None]]:
    return list(_sinks)
