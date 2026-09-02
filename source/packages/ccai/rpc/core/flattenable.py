"""
.. module:: flattenable
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: Module that contains the Flattenable protocol implemented by objects passed by value.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []


from typing import Protocol

from ccai.errors.exceptions import AbstractMethodError

class Flattenable(Protocol):

    def flatten(self):
        """
            The `flatten` method is implemented in order to customize the flatenning of an object.
        """
        thistype = type(self)

        errmsg = f"The 'flatten' method must be implemented for type='{thistype.__name__}'"
        
        raise AbstractMethodError(errmsg)




