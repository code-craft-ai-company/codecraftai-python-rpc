"""
.. module:: flattenable
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The Flattenable protocol implemented by user types that are passed by value.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Protocol, runtime_checkable

from ccai.rpc.errors import AbstractMethodError


@runtime_checkable
class Flattenable(Protocol):
    """
        A type that can be flattened to a dictionary of by-value types and rebuilt from one.
    """

    def flatten(self) -> dict:
        thistype = type(self)
        raise AbstractMethodError("The 'flatten' method must be implemented for type='{}'".format(thistype.__name__))

    @classmethod
    def unflatten(cls, data: dict) -> "Flattenable":
        raise AbstractMethodError("The 'unflatten' class method must be implemented for type='{}'".format(cls.__name__))
