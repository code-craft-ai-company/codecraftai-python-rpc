"""
.. module:: placeholder
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The encoded stand-in for an object passed by reference.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from dataclasses import dataclass

import uuid


@dataclass(frozen=True)
class ReferencePlaceholder:
    """
        Travels in place of a ByRef object: the reference id, the owning session id and the type name.
    """
    ref_id: uuid.UUID
    session_id: uuid.UUID
    type_name: str
