"""
Coordinator dispatch queue and concurrency guards.
"""

from __future__ import annotations

import threading
from contextlib import contextmanager
from dataclasses import dataclass


@dataclass
class QueueStats:
    inflight: int
    peak_inflight: int
    global_limit: int


class DispatchQueue:
    """Concurrency controls for team dispatch operations."""

    def __init__(
        self,
        *,
        global_limit: int = 2,
        per_agent_serial: bool = True,
        per_workspace_serial: bool = True,
    ) -> None:
        safe_limit = max(1, int(global_limit))
        self.global_limit = safe_limit
        self.per_agent_serial = bool(per_agent_serial)
        self.per_workspace_serial = bool(per_workspace_serial)
        self._global = threading.Semaphore(safe_limit)
        self._agent_locks: dict[str, threading.Lock] = {}
        self._workspace_locks: dict[str, threading.Lock] = {}
        self._state_lock = threading.Lock()
        self._inflight = 0
        self._peak_inflight = 0

    def _get_agent_lock(self, agent_id: str) -> threading.Lock:
        with self._state_lock:
            lock = self._agent_locks.get(agent_id)
            if lock is None:
                lock = threading.Lock()
                self._agent_locks[agent_id] = lock
            return lock

    def _get_workspace_lock(self, workspace_key: str) -> threading.Lock:
        with self._state_lock:
            lock = self._workspace_locks.get(workspace_key)
            if lock is None:
                lock = threading.Lock()
                self._workspace_locks[workspace_key] = lock
            return lock

    @contextmanager
    def acquire(self, *, agent_id: str, workspace_key: str):
        self._global.acquire()
        agent_lock = self._get_agent_lock(agent_id) if self.per_agent_serial else None
        workspace_lock = (
            self._get_workspace_lock(workspace_key) if self.per_workspace_serial else None
        )
        try:
            if agent_lock is not None:
                agent_lock.acquire()
            if workspace_lock is not None:
                workspace_lock.acquire()
            with self._state_lock:
                self._inflight += 1
                if self._inflight > self._peak_inflight:
                    self._peak_inflight = self._inflight
            yield
        finally:
            with self._state_lock:
                self._inflight = max(0, self._inflight - 1)
            if workspace_lock is not None:
                workspace_lock.release()
            if agent_lock is not None:
                agent_lock.release()
            self._global.release()

    def snapshot(self) -> dict[str, int]:
        with self._state_lock:
            stats = QueueStats(
                inflight=self._inflight,
                peak_inflight=self._peak_inflight,
                global_limit=self.global_limit,
            )
        return {
            "inflight": stats.inflight,
            "peak_inflight": stats.peak_inflight,
            "global_limit": stats.global_limit,
        }
