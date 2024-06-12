

MSG_TYPE_REQUEST = 1
MSG_TYPE_REPLY = 2
MSG_TYPE_EXCEPTION = 3


REQ_CODE_PING = 1
REQ_CODE_CLOSE = 2
REQ_CODE_GETSERVICE = 3
REQ_CODE_DELATTR = 4
REQ_CODE_GETATTR = 5
REQ_CODE_SETATTR = 6
REQ_CODE_CALL = 7


class RequestPing:

    __slots__ = ("TYPE", "CODE")

    TYPE = MSG_TYPE_REQUEST
    CODE = REQ_CODE_PING


class RequestClose:

    __slots__ = ("TYPE", "CODE")

    TYPE = MSG_TYPE_REQUEST
    CODE = REQ_CODE_CLOSE


class RequestGetService:

    __slots__ = ("TYPE", "CODE")

    TYPE = MSG_TYPE_REQUEST
    CODE = REQ_CODE_GETSERVICE


class RequestAttrDel:

    __slots__ = ("TYPE", "CODE", "attrname")

    TYPE = MSG_TYPE_REQUEST
    CODE = REQ_CODE_DELATTR

    def __init__(self, attrname: str) -> None:
        self.attrname = attrname
        return


class RequestAttrGet:

    __slots__ = ("TYPE", "CODE", "attrname")

    TYPE = MSG_TYPE_REQUEST
    CODE = REQ_CODE_GETATTR

    def __init__(self, attrname: str) -> None:
        self.attrname = attrname
        return


class RequestAttrSet:

    __slots__ = ("TYPE", "CODE", "attrname", "attrval")

    TYPE = MSG_TYPE_REQUEST
    CODE = REQ_CODE_SETATTR

    def __init__(self, attrname: str, attrval: object) -> None:
        self.attrname = attrname
        self.attrval = attrval
        return


class RequestCall:

    __slots__ = ("TYPE", "CODE", "callable_name", "args", "kwargs")

    TYPE = MSG_TYPE_REQUEST
    CODE = REQ_CODE_CALL

    def __init__(self, callable_name: str, args: list, kwargs: dict) -> None:
        self.callable_name = callable_name
        self.args = args
        self.kwargs = kwargs
        return

