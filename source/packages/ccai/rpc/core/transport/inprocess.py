"""
.. module:: inprocess
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Two connected transports in one process, for testing the full stack without a network.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Optional, Tuple

import socket

from ccai.rpc.core.transport.socketio import DuplexSocketIO


def create_socketpair_transports(receive_timeout: Optional[float] = None) -> Tuple[DuplexSocketIO, DuplexSocketIO]:
    left, right = socket.socketpair()
    return DuplexSocketIO(left, receive_timeout=receive_timeout), DuplexSocketIO(right, receive_timeout=receive_timeout)
