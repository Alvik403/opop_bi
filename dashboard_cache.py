from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from threading import RLock
from typing import Callable


Payload = tuple[dict, dict, dict]


@dataclass(frozen=True)
class CacheKey:
    file_id: int
    mtime: float
    size: int


class DashboardPayloadCache:
    def __init__(self) -> None:
        self._lock = RLock()
        self._payloads: dict[int, tuple[CacheKey, Payload]] = {}

    def get(self, file_id: int, path: Path, loader: Callable[[Path], Payload]) -> Payload:
        stat = path.stat()
        key = CacheKey(file_id=file_id, mtime=stat.st_mtime, size=stat.st_size)

        with self._lock:
            cached = self._payloads.get(file_id)
            if cached and cached[0] == key:
                return cached[1]

        payload = loader(path)
        with self._lock:
            self._payloads[file_id] = (key, payload)
        return payload

    def invalidate(self, file_id: int) -> None:
        with self._lock:
            self._payloads.pop(file_id, None)

    def clear(self) -> None:
        with self._lock:
            self._payloads.clear()
