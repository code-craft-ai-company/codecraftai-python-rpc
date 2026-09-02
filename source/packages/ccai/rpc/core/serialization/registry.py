"""
.. module:: registry
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The table of user types the codec may encode: enums, Flattenable classes and dataclasses.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Dict, Type

import dataclasses
import enum
import threading

from ccai.rpc.errors import SerializationError

_lock = threading.Lock()
_enums_by_tag: Dict[str, Type[enum.Enum]] = {}
_enum_tags: Dict[Type[enum.Enum], str] = {}
_flattenables_by_tag: Dict[str, type] = {}
_flattenable_tags: Dict[type, str] = {}


def register_enum(tag: str, cls: Type[enum.Enum]) -> None:
    if not (isinstance(cls, type) and issubclass(cls, enum.Enum)):
        raise SerializationError("register_enum expects an Enum subclass, got {!r}".format(cls))
    with _lock:
        _enums_by_tag[tag] = cls
        _enum_tags[cls] = tag
    return


def register_flattenable(tag: str, cls: type) -> None:
    if not (hasattr(cls, "flatten") and hasattr(cls, "unflatten")):
        raise SerializationError("register_flattenable expects a class with 'flatten' and 'unflatten', got {!r}".format(cls))
    with _lock:
        _flattenables_by_tag[tag] = cls
        _flattenable_tags[cls] = tag
    return


def register_dataclass(tag: str, cls: type) -> None:
    """
        Generates ``flatten`` and ``unflatten`` for a dataclass whose fields are by-value types.
    """
    if not dataclasses.is_dataclass(cls):
        raise SerializationError("register_dataclass expects a dataclass, got {!r}".format(cls))
    names = [f.name for f in dataclasses.fields(cls)]

    def flatten(self) -> dict:
        return {name: getattr(self, name) for name in names}

    def unflatten(klass, data: dict):
        return klass(**data)

    if not hasattr(cls, "flatten"):
        cls.flatten = flatten
    if not hasattr(cls, "unflatten"):
        cls.unflatten = classmethod(unflatten)
    register_flattenable(tag, cls)
    return


def enum_tag_for(cls: type):
    return _enum_tags.get(cls)


def enum_for_tag(tag: str):
    return _enums_by_tag.get(tag)


def flattenable_tag_for(cls: type):
    for klass in cls.__mro__:
        tag = _flattenable_tags.get(klass)
        if tag is not None:
            return tag
    return None


def flattenable_for_tag(tag: str):
    return _flattenables_by_tag.get(tag)
