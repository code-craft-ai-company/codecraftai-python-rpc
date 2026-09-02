"""
    Unit tests for :mod:`ccai.rpc.core.protocol` covering the framing constants and the
    construction of the request and reply message classes.
"""

import unittest

from ccai.rpc.core import protocol


class TestProtocolConstants(unittest.TestCase):
    """
        Verify the message framing constants have the layout the sessions rely on.
    """

    def test_message_types_are_distinct(self) -> None:
        types = {protocol.MSG_TYPE_REQUEST, protocol.MSG_TYPE_REPLY, protocol.MSG_TYPE_EXCEPTION}
        self.assertEqual(len(types), 3)
        return

    def test_request_codes_are_distinct(self) -> None:
        codes = [
            protocol.REQ_CODE_PING,
            protocol.REQ_CODE_CLOSE,
            protocol.REQ_CODE_GETSERVICE,
            protocol.REQ_CODE_DELATTR,
            protocol.REQ_CODE_GETATTR,
            protocol.REQ_CODE_SETATTR,
            protocol.REQ_CODE_CALL,
        ]
        self.assertEqual(len(codes), len(set(codes)))
        return

    def test_prefix_size_covers_type_code_and_origin(self) -> None:
        self.assertEqual(protocol.MessageBase.PREFIX_SIZE, 4 + 4 + len(protocol.FMT_MSG_UUID))
        return


class TestRequestMessages(unittest.TestCase):
    """
        Verify each request message class stamps the correct type and code.
    """

    def setUp(self) -> None:
        self.origin = "0f9b6b4e-1a2b-4c3d-8e9f-0a1b2c3d4e5f"
        return

    def test_ping_request(self) -> None:
        msg = protocol.RequestPing(self.origin)
        self.assertEqual(msg.mtype, protocol.MSG_TYPE_REQUEST)
        self.assertEqual(msg.mcode, protocol.REQ_CODE_PING)
        self.assertEqual(msg.origin, self.origin)
        return

    def test_close_request(self) -> None:
        msg = protocol.RequestClose(self.origin)
        self.assertEqual(msg.mtype, protocol.MSG_TYPE_REQUEST)
        self.assertEqual(msg.mcode, protocol.REQ_CODE_CLOSE)
        return

    def test_get_service_request(self) -> None:
        msg = protocol.RequestGetService(self.origin)
        self.assertEqual(msg.mtype, protocol.MSG_TYPE_REQUEST)
        self.assertEqual(msg.mcode, protocol.REQ_CODE_GETSERVICE)
        return

    def test_attr_del_request_carries_name(self) -> None:
        msg = protocol.RequestAttrDel(self.origin, "value")
        self.assertEqual(msg.mcode, protocol.REQ_CODE_DELATTR)
        self.assertEqual(msg.attrname, "value")
        return

    def test_attr_get_request_carries_name(self) -> None:
        msg = protocol.RequestAttrGet(self.origin, "value")
        self.assertEqual(msg.mcode, protocol.REQ_CODE_GETATTR)
        self.assertEqual(msg.attrname, "value")
        return

    def test_attr_set_request_carries_name_and_value(self) -> None:
        msg = protocol.RequestAttrSet(self.origin, "value", 42)
        self.assertEqual(msg.mcode, protocol.REQ_CODE_SETATTR)
        self.assertEqual(msg.attrname, "value")
        self.assertEqual(msg.attrval, 42)
        return

    def test_call_request_carries_callable_and_arguments(self) -> None:
        msg = protocol.RequestCall(self.origin, "greet", ["world"], {"loud": True})
        self.assertEqual(msg.mcode, protocol.REQ_CODE_CALL)
        self.assertEqual(msg.callable_name, "greet")
        self.assertEqual(msg.args, ["world"])
        self.assertEqual(msg.kwargs, {"loud": True})
        return


class TestReplyMessages(unittest.TestCase):
    """
        Verify the reply message classes stamp the correct type and code.
    """

    def test_pong_reply(self) -> None:
        origin = "0f9b6b4e-1a2b-4c3d-8e9f-0a1b2c3d4e5f"
        msg = protocol.ReplyPong(origin)
        self.assertEqual(msg.mtype, protocol.MSG_TYPE_REPLY)
        self.assertEqual(msg.mcode, protocol.REPLY_CODE_PONG)
        self.assertEqual(msg.origin, origin)
        return


if __name__ == "__main__":
    unittest.main()
