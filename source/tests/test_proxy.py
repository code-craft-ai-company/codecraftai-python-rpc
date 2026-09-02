"""
    Unit tests for :mod:`ccai.rpc.core.proxy` and :mod:`ccai.rpc.core.flattenable` covering
    the passing semantics wrappers.
"""

import unittest

from ccai.errors.exceptions import AbstractMethodError

from ccai.rpc.core.flattenable import Flattenable
from ccai.rpc.core.proxy import ByRef, ByValue


class TestByRef(unittest.TestCase):
    """
        Verify :class:`ByRef` keeps the instance and assigns a unique reference id.
    """

    def test_wraps_instance(self) -> None:
        target = object()
        wrapper = ByRef(target)
        self.assertIs(wrapper._instance, target)
        return

    def test_reference_ids_are_unique(self) -> None:
        target = object()
        first = ByRef(target)
        second = ByRef(target)
        self.assertNotEqual(first._refid, second._refid)
        return


class TestByValue(unittest.TestCase):
    """
        Verify :class:`ByValue` keeps the instance.
    """

    def test_wraps_instance(self) -> None:
        target = object()
        wrapper = ByValue(target)
        self.assertIs(wrapper._instance, target)
        return


class TestFlattenable(unittest.TestCase):
    """
        Verify the :class:`Flattenable` protocol default raises for unimplemented flatten.
    """

    def test_default_flatten_raises(self) -> None:

        class Unflattened(Flattenable):
            pass

        with self.assertRaises(AbstractMethodError):
            Unflattened().flatten()
        return


class TestImports(unittest.TestCase):
    """
        Verify every module in the package imports under the ccai namespace.
    """

    def test_package_modules_import(self) -> None:
        import ccai.rpc.core.duplexclientsession
        import ccai.rpc.core.duplexserversession
        import ccai.rpc.core.duplexsocketio
        import ccai.rpc.rpcsocketclient
        import ccai.rpc.rpcsocketserver
        self.assertTrue(hasattr(ccai.rpc.rpcsocketclient, "RpcSocketClient"))
        self.assertTrue(hasattr(ccai.rpc.rpcsocketserver, "RpcSocketServer"))
        return


if __name__ == "__main__":
    unittest.main()
