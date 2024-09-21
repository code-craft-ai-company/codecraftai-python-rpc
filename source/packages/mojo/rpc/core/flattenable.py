
from typing import Protocol

from mojo.errors.exceptions import NotOverloadedError

class Flattenable(Protocol):

    def flatten(self):
        """
            The `flatten` method is implemented in order to customize the flatenning of an object.
        """
        thistype = type(self)

        errmsg = f"The 'flatten' method must be implemented for type='{thistype.__name__}'"
        
        raise NotOverloadedError(errmsg)




