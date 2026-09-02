"""
.. module:: table
    :platform: Darwin, Linux, Unix, Windows
    :synopsis: The owner-side reference table: which objects were handed to which peers, with holder counts and
               lease state per holder.

.. moduleauthor:: Myron Walker <myron.walker@gmail.com>
"""

__author__ = "Myron Walker"
__copyright__ = "Copyright 2025, Code Craft AI LLC"
__credits__ = []

from typing import Dict, Iterable, List, Optional, Tuple

import threading
import time
import uuid

from ccai.rpc.errors import LeaseExpiredError, UnknownReferenceError

ROOT_REFERENCE_ID = uuid.UUID(int=0)


class LeaseState:

    __slots__ = ("expires_at", "last_renewed_at")

    def __init__(self, duration: float) -> None:
        now = time.monotonic()
        self.expires_at = now + duration
        self.last_renewed_at = now
        return

    def renew(self, duration: float) -> None:
        now = time.monotonic()
        self.expires_at = now + duration
        self.last_renewed_at = now
        return


class ReferenceEntry:

    __slots__ = ("ref_id", "obj", "holders")

    def __init__(self, ref_id: uuid.UUID, obj: object) -> None:
        self.ref_id = ref_id
        self.obj = obj
        self.holders: Dict[uuid.UUID, LeaseState] = {}
        return


class ReferenceTable:

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._entries: Dict[uuid.UUID, ReferenceEntry] = {}
        self._ids_by_object: Dict[int, uuid.UUID] = {}
        self._tombstones: Dict[uuid.UUID, Tuple[str, float]] = {}     # expired references: type name, seconds since last renewal at expiry
        self._released: Dict[uuid.UUID, object] = {}                   # recently released objects, so a reference coming home still resolves
        return

    def _remember_released(self, ref_id: uuid.UUID, obj: object) -> None:
        if len(self._released) >= 256:
            self._released.pop(next(iter(self._released)))
        self._released[ref_id] = obj
        return

    def _remember_expired(self, ref_id: uuid.UUID, entry: "ReferenceEntry", lease: "LeaseState") -> None:
        if len(self._tombstones) >= 256:
            self._tombstones.pop(next(iter(self._tombstones)))
        self._tombstones[ref_id] = (type(entry.obj).__name__, time.monotonic() - lease.last_renewed_at)
        return

    def register(self, obj: object) -> uuid.UUID:
        """
            Returns the existing id for an already registered object, or assigns a new one.
        """
        with self._lock:
            ref_id = self._ids_by_object.get(id(obj))
            if ref_id is not None and ref_id in self._entries and self._entries[ref_id].obj is obj:
                return ref_id
            ref_id = uuid.uuid4()
            self._entries[ref_id] = ReferenceEntry(ref_id, obj)
            self._ids_by_object[id(obj)] = ref_id
            return ref_id

    def lookup(self, obj: object) -> Optional[uuid.UUID]:
        """
            The id of an already registered object, or ``None``. Never registers.
        """
        with self._lock:
            ref_id = self._ids_by_object.get(id(obj))
            if ref_id is not None and ref_id in self._entries and self._entries[ref_id].obj is obj:
                return ref_id
            return None

    def register_root(self, obj: object) -> None:
        with self._lock:
            self._entries[ROOT_REFERENCE_ID] = ReferenceEntry(ROOT_REFERENCE_ID, obj)
            self._ids_by_object[id(obj)] = ROOT_REFERENCE_ID
        return

    def has_root(self) -> bool:
        with self._lock:
            return ROOT_REFERENCE_ID in self._entries

    def resolve(self, ref_id: uuid.UUID, peer: Optional[uuid.UUID] = None) -> object:
        """
            Returns the object for ``ref_id``. With ``peer`` given, the peer must hold the reference (the root
            is exempt) and its lease must not have lapsed.
        """
        with self._lock:
            entry = self._entries.get(ref_id)
            if entry is None and peer is None and ref_id in self._released:
                return self._released[ref_id]
            if entry is None:
                tomb = self._tombstones.get(ref_id)
                if tomb is not None:
                    raise LeaseExpiredError("lease on reference {} ({}) expired; it was last renewed {:.1f}s before expiry".format(ref_id, tomb[0], tomb[1]))
                raise UnknownReferenceError("unknown or released reference {}".format(ref_id))
            if peer is not None and ref_id != ROOT_REFERENCE_ID:
                lease = entry.holders.get(peer)
                if lease is None:
                    raise UnknownReferenceError("reference {} ({}) is not held by session {}".format(
                        ref_id, type(entry.obj).__name__, peer))
                if lease.expires_at < time.monotonic():
                    raise LeaseExpiredError("lease on reference {} ({}) expired; last renewed {:.1f}s ago".format(
                        ref_id, type(entry.obj).__name__, time.monotonic() - lease.last_renewed_at))
            return entry.obj

    def add_holder(self, ref_id: uuid.UUID, peer: uuid.UUID, duration: float) -> None:
        with self._lock:
            entry = self._entries[ref_id]
            lease = entry.holders.get(peer)
            if lease is None:
                entry.holders[peer] = LeaseState(duration)
            else:
                lease.renew(duration)
        return

    def release(self, ref_id: uuid.UUID, peer: Optional[uuid.UUID] = None) -> Optional[object]:
        """
            Removes ``peer`` as a holder (or every holder). Returns the object when the entry was removed.
        """
        with self._lock:
            entry = self._entries.get(ref_id)
            if entry is None or ref_id == ROOT_REFERENCE_ID:
                return None
            if peer is None:
                entry.holders.clear()
            else:
                entry.holders.pop(peer, None)
            if not entry.holders:
                self._entries.pop(ref_id, None)
                self._ids_by_object.pop(id(entry.obj), None)
                self._remember_released(ref_id, entry.obj)
                return entry.obj
            return None

    def release_all(self) -> None:
        with self._lock:
            root = self._entries.get(ROOT_REFERENCE_ID)
            self._entries.clear()
            self._ids_by_object.clear()
            if root is not None:
                self._entries[ROOT_REFERENCE_ID] = root
                self._ids_by_object[id(root.obj)] = ROOT_REFERENCE_ID
        return

    def renew(self, peer: uuid.UUID, ref_ids: Iterable[uuid.UUID], duration: float) -> List[uuid.UUID]:
        unknown = []
        with self._lock:
            for ref_id in ref_ids:
                if ref_id == ROOT_REFERENCE_ID:
                    continue
                entry = self._entries.get(ref_id)
                lease = entry.holders.get(peer) if entry is not None else None
                if lease is None:
                    unknown.append(ref_id)
                else:
                    lease.renew(duration)
        return unknown

    def expired(self, now: Optional[float] = None) -> List[Tuple[uuid.UUID, uuid.UUID]]:
        now = time.monotonic() if now is None else now
        with self._lock:
            found = [(ref_id, peer, entry, lease) for ref_id, entry in self._entries.items() if ref_id != ROOT_REFERENCE_ID
                     for peer, lease in entry.holders.items() if lease.expires_at < now]
            for ref_id, peer, entry, lease in found:
                self._remember_expired(ref_id, entry, lease)
            return [(ref_id, peer) for ref_id, peer, _, _ in found]

    def held_by(self, peer: uuid.UUID) -> List[uuid.UUID]:
        with self._lock:
            return [ref_id for ref_id, entry in self._entries.items() if peer in entry.holders]

    def describe(self) -> List[dict]:
        now = time.monotonic()
        with self._lock:
            return [{"ref_id": str(ref_id), "type": type(entry.obj).__name__, "holders": len(entry.holders),
                     "lease_expires_in": min((lease.expires_at - now for lease in entry.holders.values()), default=None)}
                    for ref_id, entry in self._entries.items()]

    def __len__(self) -> int:
        with self._lock:
            return len(self._entries)
