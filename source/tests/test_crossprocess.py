"""
    Runs the server in a separate Python process and drives it from this one, so the suite covers what a
    single-interpreter test cannot: a real process boundary, types present on one side only, and callbacks
    that cross back into the client process.
"""

import os
import platform
import pathlib
import subprocess
import sys
import threading
import time
import unittest

from ccai.rpc import AspectsRpc, RemoteError, RpcSocketClient

from crossprocess_support import Listener, Point

HERE = pathlib.Path(__file__).resolve().parent
PACKAGES = HERE.parent / "packages"


class TestCrossProcess(unittest.TestCase):

    @classmethod
    def setUpClass(cls) -> None:
        env = dict(os.environ)
        env["PYTHONPATH"] = os.pathsep.join([str(PACKAGES), str(HERE), env.get("PYTHONPATH", "")])
        cls.process = subprocess.Popen([sys.executable, str(HERE / "crossprocess_server.py")], stdout=subprocess.PIPE,
                                       stderr=subprocess.PIPE, env=env, text=True)
        port = cls._read_port(timeout=20)
        aspects = AspectsRpc(max_attempts=10, completion_interval=0.2, connection_timeout=5.0, completion_timeout=10.0,
                             heartbeat_interval=0.5, inactivity_timeout=10.0, lease_duration=3.0)
        cls.client = RpcSocketClient(None, ("127.0.0.1", port), aspects=aspects)
        cls.client.connect()
        cls.service = cls.client.get_service()
        return

    @classmethod
    def _read_port(cls, timeout: float) -> int:
        result = {}

        def reader():
            line = cls.process.stdout.readline()
            result["line"] = line
        thread = threading.Thread(target=reader, daemon=True)
        thread.start()
        thread.join(timeout=timeout)
        line = result.get("line", "")
        if not line.startswith("PORT "):
            cls.process.kill()
            raise RuntimeError("server process did not announce a port; stderr:\n" + cls.process.stderr.read())
        return int(line.split()[1])

    @classmethod
    def tearDownClass(cls) -> None:
        try:
            cls.client.close()
        finally:
            if cls.process.poll() is None:
                cls.process.terminate()
                try:
                    cls.process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    cls.process.kill()
        return

    def test_service_runs_in_another_process(self) -> None:
        remote_pid = self.service.pid()
        self.assertNotEqual(remote_pid, os.getpid())
        if platform.system() != "Windows":
            # A Windows venv python.exe is a launcher that runs the interpreter
            # as a child, so the announced pid is the launcher's child there.
            self.assertEqual(remote_pid, self.process.pid)
        return

    def test_call_and_known_exception(self) -> None:
        self.assertEqual(self.service.add(40, 2), 42)
        with self.assertRaises(KeyError) as caught:
            self.service.fail_known()
        self.assertIn("raise KeyError", caught.exception.remote_traceback)
        return

    def test_exception_type_only_on_server_becomes_remote_error(self) -> None:
        with self.assertRaises(RemoteError) as caught:
            self.service.fail_custom()
        self.assertIn("ServerOnlyError", caught.exception.remote_type_name)
        self.assertIn("only defined over here", str(caught.exception))
        self.assertIn("crossprocess_server.py", caught.exception.remote_traceback)
        return

    def test_shared_dataclass_travels_by_value(self) -> None:
        moved = self.service.move(Point(1, 2), 5)
        self.assertIsInstance(moved, Point)
        self.assertEqual(moved, Point(6, 2))
        return

    def test_acknowledged_callback_crosses_processes(self) -> None:
        listener = Listener()
        self.assertEqual(self.service.call_back(listener), 21)
        return

    def test_one_way_callbacks_arrive_in_order(self) -> None:
        listener = Listener()
        self.assertEqual(self.service.notify(listener, 15), "sent")
        deadline = time.monotonic() + 5
        while len(listener.events) < 15 and time.monotonic() < deadline:
            time.sleep(0.02)
        self.assertEqual(listener.events, list(range(15)))
        return

    def test_zz_shutdown_exits_process_cleanly(self) -> None:
        self.assertEqual(self.service.shutdown(), "stopping")
        try:
            code = self.process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            self.fail("server process did not exit after shutdown; stderr:\n" + self.process.stderr.read())
        self.assertEqual(code, 0, self.process.stderr.read())
        return


if __name__ == "__main__":
    unittest.main()
