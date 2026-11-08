"""Window-scoped admission, independent of Qt and workflow state machines.

A workflow reserves a lease; each process additionally claims that lease. Scans
keep the reservation between points. Only the exact issued objects can release
either level, so a late completion cannot free a subsequent holder. Calls belong
to the window's Qt thread; this is admission, not a process owner or global lock.
"""

from __future__ import annotations


class BackendRunOwnership:
    def __init__(self) -> None:
        self._lease: object | None = None
        self._claim: object | None = None

    @property
    def busy(self) -> bool:
        return self._lease is not None

    def acquire(self) -> object | None:
        if self.busy:
            return None
        self._lease = object()
        return self._lease

    def claim(self, lease: object) -> object | None:
        if lease is None or lease is not self._lease or self._claim is not None:
            return None
        self._claim = object()
        return self._claim

    def release_claim(self, lease: object, claim: object) -> bool:
        if (lease is None or claim is None or lease is not self._lease
                or claim is not self._claim):
            return False
        self._claim = None
        return True

    def release(self, lease: object) -> bool:
        if lease is None or lease is not self._lease or self._claim is not None:
            return False
        self._lease = None
        return True
