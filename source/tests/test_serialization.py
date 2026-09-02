"""
    Unit tests for :mod:`ccai.rpc.core.serialization`.
"""

import dataclasses
import datetime
import enum
import unittest
import uuid

from ccai.errors.exceptions import SemanticError

from ccai.rpc.errors import RemoteError, SerializationError
from ccai.rpc.core.flattenable import Flattenable
from ccai.rpc.core.proxy.wrappers import ByRef, ByValue, by_ref
from ccai.rpc.core.serialization import (
    FORMAT_VERSION, MAX_DEPTH, ReferencePlaceholder, decode, encode, register_dataclass, register_enum,
    register_flattenable,
)


class Color(enum.Enum):
    RED = 1
    BLUE = 2


register_enum("tests.color", Color)


@dataclasses.dataclass
class Point:
    x: int
    y: int


register_dataclass("tests.point", Point)


class Options:

    def __init__(self, retries: int, name: str) -> None:
        self.retries = retries
        self.name = name
        return

    def flatten(self) -> dict:
        return {"retries": self.retries, "name": self.name}

    @classmethod
    def unflatten(cls, data: dict) -> "Options":
        return cls(**data)

    def __eq__(self, other) -> bool:
        return isinstance(other, Options) and (self.retries, self.name) == (other.retries, other.name)


register_flattenable("tests.options", Options)


class TestScalars(unittest.TestCase):

    def test_scalar_round_trips(self) -> None:
        for value in (None, True, False, 0, 1, -1, 2 ** 70, -(2 ** 70), 0.0, 3.25, -1e300, "", "héllo", b"", b"\x00\xff"):
            with self.subTest(value=value):
                self.assertEqual(decode(encode(value)), value)
        return

    def test_int_and_bool_distinguished(self) -> None:
        self.assertIs(decode(encode(True)), True)
        self.assertIsInstance(decode(encode(1)), int)
        self.assertNotIsInstance(decode(encode(1)), bool)
        return

    def test_format_version_prefix(self) -> None:
        self.assertEqual(encode(None)[0], FORMAT_VERSION)
        with self.assertRaises(SerializationError):
            decode(bytes([FORMAT_VERSION + 1, 0]))
        return

    def test_unknown_type_names_type_and_path(self) -> None:
        with self.assertRaises(SerializationError) as caught:
            encode({"options": {"listener": object()}})
        self.assertIn("object", str(caught.exception))
        self.assertIn("value.options.listener", str(caught.exception))
        return


class TestContainersAndTimes(unittest.TestCase):

    def test_container_types_preserved(self) -> None:
        value = {"list": [1, 2], "tuple": (1, 2), "set": {1, 2}, "frozenset": frozenset({3}), "nested": {"a": [(1, {"b": None})]}}
        result = decode(encode(value))
        self.assertEqual(result, value)
        self.assertIsInstance(result["tuple"], tuple)
        self.assertIsInstance(result["set"], set)
        self.assertIsInstance(result["frozenset"], frozenset)
        return

    def test_dict_keys_must_be_strings(self) -> None:
        with self.assertRaises(SerializationError):
            encode({1: "a"})
        return

    def test_depth_limit(self) -> None:
        value = []
        for _ in range(MAX_DEPTH + 2):
            value = [value]
        with self.assertRaises(SerializationError):
            encode(value)
        return

    def test_time_types(self) -> None:
        aware = datetime.datetime(2026, 9, 2, 10, 30, tzinfo=datetime.timezone(datetime.timedelta(hours=-7)))
        value = {"dt": aware, "d": datetime.date(2026, 9, 2), "td": datetime.timedelta(seconds=90.5), "u": uuid.uuid4()}
        self.assertEqual(decode(encode(value)), value)
        return

    def test_naive_datetime_rejected(self) -> None:
        with self.assertRaises(SerializationError):
            encode(datetime.datetime(2026, 9, 2))
        return


class TestRegisteredTypes(unittest.TestCase):

    def test_enum_round_trip(self) -> None:
        self.assertIs(decode(encode(Color.BLUE)), Color.BLUE)
        return

    def test_unregistered_enum_rejected(self) -> None:
        class Other(enum.Enum):
            A = 1
        with self.assertRaises(SerializationError):
            encode(Other.A)
        return

    def test_flattenable_round_trip(self) -> None:
        self.assertEqual(decode(encode(Options(3, "x"))), Options(3, "x"))
        return

    def test_dataclass_helper(self) -> None:
        self.assertEqual(decode(encode(Point(1, -2))), Point(1, -2))
        return

    def test_unregistered_tag_on_decode(self) -> None:
        data = bytearray(encode(Point(1, 2)))
        data = data.replace(b"tests.point", b"tests.nopes")
        with self.assertRaises(SerializationError):
            decode(bytes(data))
        return

    def test_flattenable_protocol_default_raises(self) -> None:
        from ccai.rpc.errors import AbstractMethodError

        class Plain(Flattenable):
            pass
        with self.assertRaises(AbstractMethodError):
            Plain().flatten()
        return


class TestExceptions(unittest.TestCase):

    def test_known_ccai_type_rebuilt_with_traceback(self) -> None:
        try:
            raise SemanticError("bad thing")
        except SemanticError as exc:
            result = decode(encode(exc))
        self.assertIsInstance(result, SemanticError)
        self.assertEqual(str(result), "bad thing")
        self.assertIn("raise SemanticError", result.remote_traceback)
        return

    def test_builtin_type_rebuilt(self) -> None:
        result = decode(encode(KeyError("missing")))
        self.assertIsInstance(result, KeyError)
        return

    def test_unknown_type_becomes_remote_error(self) -> None:
        class Weird(Exception):
            pass
        result = decode(encode(Weird("odd")))
        self.assertIsInstance(result, RemoteError)
        self.assertIn("Weird", result.remote_type_name)
        self.assertIn("odd", str(result))
        return


class TestReferences(unittest.TestCase):

    def test_placeholder_round_trip_through_resolver(self) -> None:
        placeholder = ReferencePlaceholder(uuid.uuid4(), uuid.uuid4(), "Listener")
        seen = []
        result = decode(encode(placeholder), resolver=lambda p: seen.append(p) or "proxy")
        self.assertEqual(result, "proxy")
        self.assertEqual(seen, [placeholder])
        return

    def test_placeholder_without_resolver_raises(self) -> None:
        with self.assertRaises(SerializationError):
            decode(encode(ReferencePlaceholder(uuid.uuid4(), uuid.uuid4(), "X")))
        return

    def test_by_ref_uses_reference_encoder(self) -> None:
        target = object()
        placeholder = ReferencePlaceholder(uuid.uuid4(), uuid.uuid4(), "object")
        data = encode({"cb": ByRef(target)}, ref_encoder=lambda obj: placeholder if obj is target else None)
        self.assertEqual(decode(data, resolver=lambda p: p), {"cb": placeholder})
        return

    def test_by_ref_type_decorator(self) -> None:
        @by_ref
        class Listener:
            pass
        listener = Listener()
        placeholder = ReferencePlaceholder(uuid.uuid4(), uuid.uuid4(), "Listener")
        data = encode(listener, ref_encoder=lambda obj: placeholder if obj is listener else None)
        self.assertEqual(decode(data, resolver=lambda p: p), placeholder)
        return

    def test_by_ref_without_session_raises(self) -> None:
        with self.assertRaises(SerializationError):
            encode(ByRef(object()))
        return

    def test_by_value_is_transparent(self) -> None:
        self.assertEqual(decode(encode(ByValue([1, 2]))), [1, 2])
        return


if __name__ == "__main__":
    unittest.main()
