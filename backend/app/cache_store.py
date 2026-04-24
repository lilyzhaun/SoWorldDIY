from __future__ import annotations

import copy
import threading
import time
from typing import Any


class MemoryCache:
    def __init__(self, default_timeout: int = 300) -> None:
        self.default_timeout = default_timeout
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, Any]] = {}

    def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        ttl = self.default_timeout if timeout is None else timeout
        with self._lock:
            self._store[key] = (time.time() + ttl, copy.deepcopy(value))

    def get(self, key: str) -> Any | None:
        with self._lock:
            cached = self._store.get(key)
            if not cached:
                return None
            expires_at, value = cached
            if time.time() >= expires_at:
                self._store.pop(key, None)
                return None
            return copy.deepcopy(value)

    def delete(self, key: str) -> None:
        with self._lock:
            self._store.pop(key, None)
