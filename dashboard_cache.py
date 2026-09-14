from __future__ import annotations

import logging
from collections import OrderedDict
from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Callable


Payload = tuple[dict, dict, dict]
logger = logging.getLogger("opop_bi.cache")


@dataclass(frozen=True)
class CacheKey:
    file_id: int
    mtime: float
    size: int


class DashboardPayloadCache:
    def __init__(self, max_entries: int = 16) -> None:
        self._max_entries = max(1, max_entries)
        self._lock = RLock()
        self._payloads: OrderedDict[int, tuple[CacheKey, Payload]] = OrderedDict()
        self._load_locks: dict[int, RLock] = {}

    def _lock_for(self, file_id: int) -> RLock:
        with self._lock:
            lock = self._load_locks.get(file_id)
            if lock is None:
                lock = RLock()
                self._load_locks[file_id] = lock
            return lock

    def _store(self, file_id: int, key: CacheKey, payload: Payload) -> None:
        self._payloads[file_id] = (key, payload)
        self._payloads.move_to_end(file_id)
        while len(self._payloads) > self._max_entries:
            evicted_id, _ = self._payloads.popitem(last=False)
            self._load_locks.pop(evicted_id, None)

    def get(self, file_id: int, path: Path, loader: Callable[[Path], Payload]) -> Payload:
        stat = path.stat()
        key = CacheKey(file_id=file_id, mtime=stat.st_mtime, size=stat.st_size)

        with self._lock:
            cached = self._payloads.get(file_id)
            if cached and cached[0] == key:
                self._payloads.move_to_end(file_id)
                logger.info("dashboard_cache_hit", extra={"file_id": file_id, "path": str(path)})
                return cached[1]

        load_lock = self._lock_for(file_id)
        with load_lock:
            with self._lock:
                cached = self._payloads.get(file_id)
                if cached and cached[0] == key:
                    self._payloads.move_to_end(file_id)
                    logger.info(
                        "dashboard_cache_hit",
                        extra={"file_id": file_id, "path": str(path)},
                    )
                    return cached[1]

            logger.info("dashboard_cache_miss", extra={"file_id": file_id, "path": str(path)})
            payload = loader(path)
            with self._lock:
                self._store(file_id, key, payload)
            return payload

    def invalidate(self, file_id: int) -> None:
        with self._lock:
            self._payloads.pop(file_id, None)
            self._load_locks.pop(file_id, None)
        logger.info("dashboard_cache_invalidated", extra={"file_id": file_id})

    def clear(self) -> None:
        with self._lock:
            self._payloads.clear()
            self._load_locks.clear()
