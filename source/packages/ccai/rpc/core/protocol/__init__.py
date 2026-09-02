"""
    The wire protocol: framing, the fixed header, the message vocabulary and the message classes.
"""

from ccai.rpc.core.protocol.constants import (
    DEFAULT_MAX_MESSAGE_SIZE, FRAME_SIZE_BYTES, HEADER_SIZE, MIN_SUPPORTED_VERSION, PROTOCOL_VERSION,
    ExceptionCode, MessageType, ReplyCode, RequestCode,
)
from ccai.rpc.core.protocol.header import MessageHeader, frame, read_frame_size
from ccai.rpc.core.protocol.messages import (
    REGISTRY, REPLY_FOR_REQUEST, ExceptionMessage, Message,
    ReplyCall, ReplyCancel, ReplyClose, ReplyDelAttr, ReplyGetAttr, ReplyGetService, ReplyHello, ReplyPing,
    ReplyProgress, ReplyRelease, ReplyRenew, ReplySetAttr,
    RequestCall, RequestCancel, RequestClose, RequestDelAttr, RequestGetAttr, RequestGetService, RequestHello,
    RequestPing, RequestProgress, RequestRelease, RequestRenew, RequestSetAttr,
)
