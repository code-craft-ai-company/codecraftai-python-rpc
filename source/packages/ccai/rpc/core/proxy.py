"""
.. module:: proxy
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Module that contains the ByRef and ByValue wrappers used to declare how an object is passed over RPC.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []


from uuid import uuid4

class ByRef:
    """
        The :class:`ByRef` object is used to wrap an object instance in order to indicate to the
        rpc protocol on how the object should be handled.
    """
    def __init__(self, instance: object):
        self._instance = instance
        self._refid = uuid4()
        return

class ByValue:
    """
        The :class:`ByValue` object is used to wrap an object instance in order to indicate to the
        rpc protocol on how the object should be handled.
    """
    def __init__(self, instance: object):
        self._instance = instance
        return


