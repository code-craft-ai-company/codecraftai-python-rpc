"""
    State dumps, metrics sinks and the wire trace logger name.
"""

from ccai.rpc.core.observability.state import dump_state, install_dump_on_signal, live_clients, live_servers
from ccai.rpc.core.observability.metrics import register_metrics_sink, metrics_sinks

WIRE_LOGGER_NAME = "ccai.rpc.wire"

__all__ = ["dump_state", "install_dump_on_signal", "live_clients", "live_servers", "register_metrics_sink", "metrics_sinks", "WIRE_LOGGER_NAME"]
