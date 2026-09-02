"""
.. module:: dispatch
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: DispatchLooper, the pool worker that decodes an inbound request, runs its handler under a call
               context and per-target ordering, and answers with a reply or an exception message.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

import time

from ccai.rpc.aspects import LoggingPattern
from ccai.rpc.errors import CancelledError, LeaseExpiredError, ProtocolError, UnauthorizedError, UnknownReferenceError
from ccai.rpc.core.dispatch.context import CallContext, set_call_context
from ccai.rpc.core.looper import Looper
from ccai.rpc.core.protocol.constants import ExceptionCode, RequestCode
from ccai.rpc.core.protocol.messages import ExceptionMessage, Message
from ccai.rpc.core.proxy.wrappers import CONCURRENT_MARKER

_TARGETED = (int(RequestCode.CALL), int(RequestCode.GETATTR), int(RequestCode.SETATTR), int(RequestCode.DELATTR))


class DispatchLooper(Looper):

    def __init__(self, queue, name=None, group=None, daemon=None, session=None, **kwargs) -> None:
        super().__init__(queue, name=name, group=group, daemon=daemon, **kwargs)
        self._session = session
        return

    def loop(self, packet) -> None:
        if callable(packet):
            packet()
            return
        session = self._session
        try:
            message = Message.unpack(packet, resolver=session.resolve_reference)
        except Exception as err:  # noqa: BLE001
            session.logger.warning("could not decode inbound request: %s", err)
            try:
                from ccai.rpc.core.protocol.header import MessageHeader
                header = MessageHeader.unpack(packet)
                session.send_exception(ExceptionMessage(code=int(ExceptionCode.PROTOCOL_ERROR), type_name="ProtocolError",
                                                        message=str(err), correlation_id=header.correlation_id))
            except Exception:  # noqa: BLE001
                pass
            return
        code = int(message.mcode)
        target_ref = getattr(message, "target_ref", None)
        lane = None
        # Ordering lanes apply to one-way callbacks only. An acknowledged call already serialises its caller,
        # and a lane on an acknowledged call would deadlock a re-entrant chain that targets the same object.
        if code in _TARGETED and target_ref is not None and getattr(message, "notify", False):
            try:
                obj = session.table.resolve(target_ref)
                if not getattr(type(obj), CONCURRENT_MARKER, False):
                    lane = session.lane_for(target_ref)
            except Exception:  # noqa: BLE001 - the handler reports the missing reference
                lane = None
        work = lambda: self._execute(session, message)  # noqa: E731
        if lane is not None:
            lane.run(work)
        else:
            work()
        return

    def _execute(self, session, message) -> None:
        code = int(message.mcode)
        notify = bool(getattr(message, "notify", False)) or code in (int(RequestCode.CANCEL), int(RequestCode.PROGRESS), int(RequestCode.CLOSE))
        deadline_remaining = getattr(message, "deadline", None)
        deadline = time.monotonic() + deadline_remaining if deadline_remaining is not None else None
        context = CallContext(session, message.correlation_id, session.peer_session_id, getattr(message, "target_ref", None),
                              getattr(message, "callable_name", None) or getattr(message, "name", None) or RequestCode(code).name,
                              deadline, caller_context={**session.peer_context, **(getattr(message, "context", None) or {})}, notify=notify)
        handler = session.handler_for(code)
        started = time.monotonic()
        outcome = "ok"
        try:
            if handler is None:
                raise ProtocolError("no handler for request code {}".format(RequestCode(code).name))
            if deadline is not None and deadline_remaining <= 0:
                raise CancelledError("deadline of call '{}' had already passed when it was received".format(context.callable_name))
            session.track_call(context)
            set_call_context(context)
            try:
                reply = handler(session, message, context)
            finally:
                set_call_context(None)
                session.untrack_call(context)
            if context.is_cancelled and code in _TARGETED:
                raise CancelledError("call '{}' was cancelled".format(context.callable_name))
            if reply is not None and not notify:
                reply.correlation_id = message.correlation_id
                session.send_reply(reply)
        except Exception as err:  # noqa: BLE001 - every failure travels back as an exception message
            outcome = type(err).__name__
            if isinstance(err, (UnknownReferenceError, LeaseExpiredError)) or (isinstance(err, AttributeError) and "refused" in str(err)):
                session.logger.warning("refused %s '%s' from %s (%s): %s", RequestCode(code).name, context.callable_name,
                                       session.peer_identity or session.peer_session_id, session.remote_address, err)
            if notify:
                session.logger.warning("one-way request %s '%s' raised: %s", RequestCode(code).name, context.callable_name, err)
            else:
                exc_code = {UnknownReferenceError: ExceptionCode.UNKNOWN_REFERENCE, LeaseExpiredError: ExceptionCode.LEASE_EXPIRED,
                            CancelledError: ExceptionCode.CANCELLED, ProtocolError: ExceptionCode.PROTOCOL_ERROR,
                            UnauthorizedError: ExceptionCode.UNAUTHORIZED}.get(type(err), ExceptionCode.REMOTE_EXCEPTION)
                try:
                    session.send_exception(ExceptionMessage.from_exception(err, code=exc_code, correlation_id=message.correlation_id))
                except Exception:  # noqa: BLE001
                    session.logger.exception("could not send exception reply for %s", context.callable_name)
        finally:
            self._log_outcome(session, code, context, time.monotonic() - started, outcome)
        return

    @staticmethod
    def _log_outcome(session, code, context, duration, outcome) -> None:
        pattern = session.aspects.logging_pattern
        failed = outcome != "ok"
        if pattern == LoggingPattern.ALL_RESULTS or (failed and pattern == LoggingPattern.FAILURE_ONLY) or (not failed and pattern == LoggingPattern.SUCCESS_ONLY):
            session.logger.info("%s %s target=%s caller=%s %.3fs %s", RequestCode(code).name, context.callable_name,
                                context.target_ref, context.caller_session_id, duration, outcome)
        return
