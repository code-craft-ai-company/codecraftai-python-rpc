"""
.. module:: auth
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The authenticator hook the server calls during HELLO, and a constant-time shared-secret implementation.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Callable, Optional, Tuple

import hmac

Authenticator = Callable[[bytes, Tuple[str, int]], Optional[str]]


def shared_secret_authenticator(secret: bytes, identity: str = "shared-secret") -> Authenticator:
    """
        Accepts a credential equal to ``secret``, compared in constant time, and names the peer ``identity``.
    """
    if isinstance(secret, str):
        secret = secret.encode("utf-8")

    def authenticate(credential: bytes, address: Tuple[str, int]) -> Optional[str]:
        if credential is None:
            return None
        if isinstance(credential, str):
            credential = credential.encode("utf-8")
        return identity if hmac.compare_digest(bytes(credential), secret) else None

    return authenticate
