"""
    Types shared by both sides of the cross-process test. Both processes import this module, so the
    dataclass registered here travels by value between them.
"""

import dataclasses

from ccai.rpc import by_ref, register_dataclass


@dataclasses.dataclass
class Point:
    x: int
    y: int


register_dataclass("tests.crossprocess.point", Point)


@by_ref
class Listener:
    """
        Lives in the client process; the server calls back into it across the process boundary.
    """

    def __init__(self) -> None:
        self.events = []
        return

    def on_event(self, i: int) -> None:
        self.events.append(i)
        return

    def compute(self, n: int) -> int:
        return n * 7
