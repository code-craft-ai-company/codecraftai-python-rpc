"""
.. module:: tags
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The value tags and format version of the wire codec.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from enum import IntEnum

FORMAT_VERSION = 1
MAX_DEPTH = 64


class Tag(IntEnum):
    NONE = 0
    TRUE = 1
    FALSE = 2
    INT = 3
    FLOAT = 4
    STR = 5
    BYTES = 6
    LIST = 7
    TUPLE = 8
    DICT = 9
    SET = 10
    FROZENSET = 11
    DATETIME = 12
    DATE = 13
    TIMEDELTA = 14
    UUID = 15
    ENUM = 16
    FLATTENABLE = 17
    EXCEPTION = 18
    REFERENCE = 19
