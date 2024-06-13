
import struct

from uuid import uuid4


FMT_MSG_SIZE = "!Q"
FMT_MSG_UINT = "!I"
FMT_MSG_UUID = "s" * len(str(uuid4()))


MSG_TYPE_REQUEST = 1
MSG_TYPE_REPLY = 2
MSG_TYPE_EXCEPTION = 3


REPLY_CODE_PONG = 1


REQ_CODE_PING = 1
REQ_CODE_CLOSE = 2
REQ_CODE_GETSERVICE = 3
REQ_CODE_DELATTR = 4
REQ_CODE_GETATTR = 5
REQ_CODE_SETATTR = 6
REQ_CODE_CALL = 7



class MessageBase:

    PREFIX_SIZE = 4 + 4 + len(FMT_MSG_UUID)

    def pack_prefix(self, buffer) -> bytes:

        ppos = 0
        
        struct.pack_into(FMT_MSG_UINT, buffer, ppos, self.mtype)
        ppos += 4

        struct.pack_into(FMT_MSG_UINT, buffer, ppos, self.mcode)
        ppos += 4

        struct.pack_into(FMT_MSG_UUID, buffer, ppos, self.origin)

        return ppos



class ReplyPong(MessageBase):

    __slots__ = ("mtype", "mcode", "origin")
    
    

    def __init__(self, origin: str):
        self.mtype = MSG_TYPE_REPLY
        self.mcode = REPLY_CODE_PONG
        self.origin = origin
        return
    
    def pack(self) -> bytes:

        buffer = bytearray(self.PREFIX_SIZE)

        ppos = self.pack_prefix(buffer)

        return buffer



class RequestPing(MessageBase):

    __slots__ = ("mtype", "mcode", "origin")
    
    def __init__(self, origin: str):
        self.mtype = MSG_TYPE_REQUEST
        self.mcode = REQ_CODE_PING
        self.origin = origin
        return
    
    def pack(self) -> bytes:

        buffer = bytearray(self.PREFIX_SIZE)

        ppos = self.pack_prefix(buffer)

        return buffer

class RequestClose(MessageBase):

    __slots__ = ("mtype", "mcode", "origin")

    PREFIX_SIZE = 4 + 4 + len(FMT_MSG_UUID)

    def __init__(self, origin: str):
        self.mtype = MSG_TYPE_REQUEST
        self.mcode = REQ_CODE_CLOSE
        self.origin = origin
        return
    
    def pack(self) -> bytes:

        buffer = bytearray(self.PREFIX_SIZE)

        ppos = self.pack_prefix(buffer)

        return buffer


class RequestGetService(MessageBase):

    __slots__ = ("mtype", "mcode", "origin")

    PREFIX_SIZE = 4 + 4 + len(FMT_MSG_UUID)

    def __init__(self, origin: str):
        self.mtype = MSG_TYPE_REQUEST
        self.mcode = REQ_CODE_GETSERVICE
        self.origin = origin
        return
    
    def pack(self) -> bytes:

        buffer = bytearray(self.PREFIX_SIZE)

        ppos = self.pack_prefix(buffer)

        return buffer


class RequestAttrDel(MessageBase):

    __slots__ = ("mtype", "mcode", "origin", "attrname")

    PREFIX_SIZE = 4 + 4 + len(FMT_MSG_UUID)

    def __init__(self, origin: str, attrname: str):
        self.mtype = MSG_TYPE_REQUEST
        self.mcode = REQ_CODE_DELATTR
        self.origin = origin
        self.attrname = attrname
        return
    
    def pack(self) -> bytes:

        buffer = bytearray(self.PREFIX_SIZE)

        ppos = self.pack_prefix(buffer)

        return buffer


class RequestAttrGet(MessageBase):

    __slots__ = ("mtype", "mcode", "origin", "attrname")

    PREFIX_SIZE = 4 + 4 + len(FMT_MSG_UUID)

    def __init__(self, origin: str, attrname: str):
        self.mtype = MSG_TYPE_REQUEST
        self.mcode = REQ_CODE_GETATTR
        self.origin = origin
        self.attrname = attrname
        return
    
    def pack(self) -> bytes:

        buffer = bytearray(self.PREFIX_SIZE)

        ppos = self.pack_prefix(buffer)

        return buffer


class RequestAttrSet(MessageBase):

    __slots__ = ("mtype", "mcode", "origin", "attrname", "attrval")

    PREFIX_SIZE = 4 + 4 + len(FMT_MSG_UUID)

    def __init__(self, origin: str, attrname: str, attrval: object):
        self.mtype = MSG_TYPE_REQUEST
        self.mcode = REQ_CODE_SETATTR
        self.origin = origin
        self.attrname = attrname
        self.attrval = attrval
        return
    
    def pack(self) -> bytes:

        buffer = bytearray(self.PREFIX_SIZE)

        ppos = self.pack_prefix(buffer)

        return buffer


class RequestCall(MessageBase):

    __slots__ = ("mtype", "mcode", "origin", "callable_name", "args", "kwargs")

    PREFIX_SIZE = 4 + 4 + len(FMT_MSG_UUID)

    def __init__(self, origin: str, callable_name: str, args: list, kwargs: dict):
        self.mtype = MSG_TYPE_REQUEST
        self.mcode = REQ_CODE_CALL
        self.origin = origin
        self.callable_name = callable_name
        self.args = args
        self.kwargs = kwargs
        return
    
    def pack(self) -> bytes:

        buffer = bytearray(self.PREFIX_SIZE)

        ppos = self.pack_prefix(buffer)

        return buffer

