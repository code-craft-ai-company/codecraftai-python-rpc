"""
    Unit tests for :mod:`ccai.rpc.core.protocol`.
"""

import unittest
import uuid

from ccai.rpc.errors import ProtocolError
from ccai.rpc.core.protocol import (
    DEFAULT_MAX_MESSAGE_SIZE, HEADER_SIZE, PROTOCOL_VERSION, REGISTRY, REPLY_FOR_REQUEST, ExceptionCode, ExceptionMessage,
    Message, MessageHeader, MessageType, ReplyCall, ReplyHello, ReplyRenew, RequestCall, RequestCode, RequestGetAttr,
    RequestHello, RequestPing, RequestProgress, RequestRenew, RequestSetAttr, frame, read_frame_size,
)


class TestHeader(unittest.TestCase):

    def test_round_trip(self) -> None:
        header = MessageHeader(PROTOCOL_VERSION, MessageType.REPLY, 8, uuid.uuid4(), 42)
        packed = header.pack()
        self.assertEqual(len(packed), HEADER_SIZE)
        self.assertEqual(MessageHeader.unpack(packed), header)
        return

    def test_short_data_rejected(self) -> None:
        with self.assertRaises(ProtocolError):
            MessageHeader.unpack(b"\x00" * (HEADER_SIZE - 1))
        return

    def test_bad_version_rejected(self) -> None:
        packed = bytearray(MessageHeader(PROTOCOL_VERSION, MessageType.REQUEST, 1, uuid.uuid4(), 0).pack())
        packed[0:2] = (99).to_bytes(2, "big")
        with self.assertRaises(ProtocolError) as caught:
            MessageHeader.unpack(bytes(packed))
        self.assertIn("99", str(caught.exception))
        return

    def test_bad_type_rejected(self) -> None:
        packed = bytearray(MessageHeader(PROTOCOL_VERSION, MessageType.REQUEST, 1, uuid.uuid4(), 0).pack())
        packed[2] = 9
        with self.assertRaises(ProtocolError):
            MessageHeader.unpack(bytes(packed))
        return


class TestFraming(unittest.TestCase):

    def test_frame_prefixes_size(self) -> None:
        framed = frame(b"abc")
        self.assertEqual(read_frame_size(framed[:8]), 3)
        self.assertEqual(framed[8:], b"abc")
        return

    def test_zero_length_rejected(self) -> None:
        with self.assertRaises(ProtocolError):
            frame(b"")
        with self.assertRaises(ProtocolError):
            read_frame_size((0).to_bytes(8, "big"))
        return

    def test_size_limit(self) -> None:
        with self.assertRaises(ProtocolError):
            read_frame_size((DEFAULT_MAX_MESSAGE_SIZE + 1).to_bytes(8, "big"))
        self.assertEqual(read_frame_size((10).to_bytes(8, "big"), max_message_size=10), 10)
        return


class TestMessages(unittest.TestCase):

    def test_every_class_round_trips(self) -> None:
        samples = {
            "RequestHello": RequestHello(session_id=uuid.uuid4(), credential=b"tok", context={"run": "r1"}),
            "RequestPing": RequestPing(),
            "RequestGetAttr": RequestGetAttr(uuid.uuid4(), "name", 5.0, {}),
            "RequestSetAttr": RequestSetAttr(uuid.uuid4(), "name", 42, None, {}),
            "RequestCall": RequestCall(uuid.uuid4(), "greet", ("world",), {"loud": True}, 5.0, {}, False),
            "RequestRenew": RequestRenew(ref_ids=(uuid.uuid4(), uuid.uuid4())),
            "RequestProgress": RequestProgress(uuid.uuid4(), 0.5, "half", {"step": 2}),
            "ReplyHello": ReplyHello(chosen_version=1, session_id=uuid.uuid4(), lease_duration=90.0, heartbeat_interval=10.0),
            "ReplyCall": ReplyCall(value=[1, 2, 3]),
            "ReplyRenew": ReplyRenew(unknown=(uuid.uuid4(),)),
        }
        for name, msg in samples.items():
            with self.subTest(message=name):
                back = Message.unpack(msg.pack())
                self.assertEqual(back, msg)
                self.assertIs(type(back), type(msg))
        return

    def test_registry_covers_every_request_and_reply(self) -> None:
        for code in RequestCode:
            self.assertIn((MessageType.REQUEST, int(code)), REGISTRY)
            self.assertIn((MessageType.REPLY, int(code)), REGISTRY)
        self.assertIs(REPLY_FOR_REQUEST[int(RequestCode.CALL)], ReplyCall)
        return

    def test_unknown_pair_rejected(self) -> None:
        header = MessageHeader(PROTOCOL_VERSION, MessageType.REQUEST, 200, uuid.uuid4(), 0)
        with self.assertRaises(ProtocolError):
            Message.unpack(header.pack())
        return

    def test_length_mismatch_rejected(self) -> None:
        data = RequestCall(uuid.uuid4(), "m", (), {}, None, {}).pack()
        with self.assertRaises(ProtocolError):
            Message.unpack(data[:-1])
        return

    def test_defaults_and_unknown_fields(self) -> None:
        self.assertEqual(RequestCall(uuid.uuid4(), "m").args, ())
        self.assertFalse(RequestCall(uuid.uuid4(), "m").notify)
        with self.assertRaises(TypeError):
            RequestPing(bogus=1)
        return

    def test_exception_message_from_exception(self) -> None:
        cid = uuid.uuid4()
        try:
            raise ValueError("bad input")
        except ValueError as exc:
            msg = ExceptionMessage.from_exception(exc, code=ExceptionCode.REMOTE_EXCEPTION, correlation_id=cid)
        back = Message.unpack(msg.pack())
        self.assertEqual(back.correlation_id, cid)
        self.assertEqual(back.code, int(ExceptionCode.REMOTE_EXCEPTION))
        self.assertIsInstance(back.value, ValueError)
        self.assertIn("bad input", back.message)
        self.assertIn("raise ValueError", back.traceback_text)
        return


if __name__ == "__main__":
    unittest.main()
