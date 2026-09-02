"""
    The wire codec. ``encode`` and ``decode`` turn values into payload bytes and back using a tagged
    binary format with a closed type set; user types opt in through ``register_enum``,
    ``register_flattenable`` and ``register_dataclass``.
"""

from ccai.rpc.core.serialization.codec import decode, encode
from ccai.rpc.core.serialization.placeholder import ReferencePlaceholder
from ccai.rpc.core.serialization.registry import register_dataclass, register_enum, register_flattenable
from ccai.rpc.core.serialization.tags import FORMAT_VERSION, MAX_DEPTH, Tag

__all__ = ["encode", "decode", "ReferencePlaceholder", "register_dataclass", "register_enum",
           "register_flattenable", "FORMAT_VERSION", "MAX_DEPTH", "Tag"]
