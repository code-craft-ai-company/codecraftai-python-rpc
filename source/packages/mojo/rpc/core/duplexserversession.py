

from typing import Optional


import struct
import threading


from uuid import uuid4


from mojo.rpc.core.looperpool import LooperPool

from mojo.rpc.core.duplexsocketio import DuplexSocketIO


from mojo.rpc.core.looper import Looper
from mojo.rpc.core.looperpool import LooperPool
from mojo.rpc.core.looperqueue import LooperQueue

from mojo.rpc.core import protocol


DEFAULT_RESPONSE_TIMEOUT = 60


class ServerDispatchLooper(Looper):


    def __init__(self, queue: LooperQueue, name: Optional[str]=None, group: Optional[str]=None, daemon: Optional[bool]=None, **kwargs):
        super().__init__(queue, name=name, group=group, daemon=daemon)
        return
    

    def loop(self, session: "DuplexServerSession", packet: bytes) -> bool: # pylint: disable=no-self-use
        """
            Method that is overloaded in order to dispatch server work requests.
        """

        ppos = 0

        msg_type = struct.unpack_from("!I", packet, offset=ppos)
        ppos += 4

        if msg_type == protocol.MSG_TYPE_REPLY:
            self._process_reply(ppos, packet)
        elif msg_type == protocol.MSG_TYPE_REQUEST:
            self._process_request(session, ppos, packet)
        elif msg_type == protocol.MSG_TYPE_EXCEPTION:
            pass
        else:
            errmsg = f"Unknown message type '{msg_type}' received."
            raise RuntimeError(errmsg)

        return
    
    def _process_exception(ppos: int, packet: bytes):

        return

    def _process_reply(ppos: int, packet: bytes):

        msg_code = struct.unpack_from("!I", packet, offset=ppos)
        ppos += 4

        return

    def _process_request(self, session: "DuplexServerSession", ppos: int, packet: bytes) -> bytes:

        reply_packet = None

        msg_code = struct.unpack_from("!I", packet, offset=ppos)
        ppos += 4

        origin = struct.unpack_from(protocol.FMT_MSG_UUID, packet, offset=ppos)
        ppos += len(protocol.FMT_MSG_UUID)

        if msg_code == protocol.REQ_CODE_PING:
            reply_packet = self._process_request_ping(origin)
        elif msg_code == protocol.REQ_CODE_CLOSE:
            reply_packet = self._process_request_close(origin)
        elif msg_code == protocol.REQ_CODE_GETSERVICE:
            reply_packet = self._process_request_service_get(origin)
        elif msg_code == protocol.REQ_CODE_DELATTR:
            reply_packet = self._process_request_attr_del(origin)
        elif msg_code == protocol.REQ_CODE_GETATTR:
            reply_packet = self._process_request_attr_get(origin)
        elif msg_code == protocol.REQ_CODE_SETATTR:
            reply_packet = self._process_request_attr_set(origin)
        elif msg_code == protocol.REQ_CODE_CALL:
            reply_packet = self._process_request_call(origin)
        else:
            errmsg = f"Unknown message code {msg_code} received."
            raise RuntimeError(errmsg)

        session.reply_message(reply_packet)

        return

    def _process_request_attr_del(self, origin: str) -> bytes:

        reply_packet = b""

        return reply_packet
    
    def _process_request_attr_get(self, origin: str) -> bytes:

        reply_packet = b""

        return reply_packet
    
    def _process_request_attr_set(self, origin: str) -> bytes:

        reply_packet = b""

        return reply_packet

    def _process_request_call(self, origin: str) -> bytes:

        reply_packet = b""

        return reply_packet
    
    def _process_request_close(self, origin: str) -> bytes:

        reply_packet = b""

        return reply_packet

    def _process_request_ping(self, origin: str) -> bytes:

        reply = protocol.ReplyPong(origin)
        reply_packet = reply.pack()

        return reply_packet
    
    def _process_request_service_get(self, origin: str) -> bytes:

        reply_packet = b""

        return reply_packet


class DuplexServerSession:


    def __init__(self, sockio: DuplexSocketIO):

        self._sockio = sockio

        self._lock = threading.Lock()

        self._waiter_gates = {}
        self._responses = {}

        self._running = False

        self._transmit_queue = []
        self._transmit_available = threading.Semaphore(0)

        self._dispatch_pool = None
        
        self._receive_thread = None
        self._transmit_thread = None

        return


    def start(self):

        # Start the dispatch thread pool first
        self._dispatch_pool = LooperPool(ServerDispatchLooper, "rpc-server-dispatch", daemon=True)
        self._dispatch_pool.start_pool()


        sgate = threading.Event()

        # Next start the receive thread
        sgate.clear()
        self._receive_thread = threading.Thread(target=self._receive_loop, name="rpc-server-recv", args=(sgate,), daemon=True)
        sgate.wait()

        # Finally start the transmit thread, We dont use the calling thread to transmit on the socket because we are
        # multiplexing the RPC traffic on the socket
        sgate.clear()
        self._transmit_thread = threading.Thread(target=self._transmit_loop, name="rpc-server-xmit", args=(sgate,), daemon=True)
        sgate.wait()

        self._running = True

        return


    def reply_message(self, message: bytes):

        self._lock.acquire()
        try:
            self._transmit_queue.append(message)
        finally:
            self._lock.release()

        # If we didn't throw an exception, we will surely get to here, no need to lock on this Semaphore
        self._transmit_available.release()

        return


    def send_message(self, message: bytes, response_timeout: float=None):

        thread_guid = None

        this_thread = threading.current_thread()
        if hasattr(this_thread, 'thread_guid'):
            thread_guid = this_thread.thread_guid
        else:
            thread_guid = uuid4()
            setattr(this_thread, "thread_guid", thread_guid)

        wgate = threading.Event()

        wgate.clear()

        self._lock.acquire()
        try:
            self._waiter_gates[thread_guid] = (this_thread, wgate)
        
            self._transmit_queue.append(message)
        finally:
            self._lock.release()

        # If we didn't throw an exception, we will surely get to here, no need to lock on this Semaphore
        self._transmit_available.release()

        wgate.wait(timeout=response_timeout)

        if thread_guid not in self._responses:
            errmsg = "No response received for call."
            raise RuntimeError(errmsg)
        
        response = self._responses.pop(thread_guid)

        return response


    def _transmit_loop(self, sgate: threading.Event):

        sgate.set()

        while self._running:

            self._transmit_available.acquire()

            message = self._transmit_queue.pop()

            self._sockio.transmit_message(message, response_timeout=DEFAULT_RESPONSE_TIMEOUT)
            # We don't look for a reply, the receive loop handles all inbound traffic

        return
    

    def _receive_loop(self, sgate: threading.Event):

        sgate.set()

        while self._running:

            bytes_received = self._sockio.receive_message()

            self._dispatch_pool.push_work(self, bytes_received)

        return
