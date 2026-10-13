from __future__ import annotations

import copy
import threading
import time
from typing import Any


def profile_cache_key(sid: str, account_id: str) -> str:
    return f"profile_{sid}_{account_id}"


class MemoryCache:
    def __init__(self, default_timeout: int = 300, max_entries: int = 256) -> None:
        self.default_timeout = default_timeout
        self.max_entries = max_entries
        self._lock = threading.Lock()
        self._store: dict[str, tuple[float, Any]] = {}

    def set(self, key: str, value: Any, timeout: int | None = None) -> None:
        ttl = self.default_timeout if timeout is None else timeout
        with self._lock:
            now = time.time()
            for expired in [
                k for k, (deadline, _) in self._store.items() if deadline <= now
            ]:
                del self._store[expired]
            if key not in self._store and len(self._store) >= self.max_entries:
                self._store.pop(next(iter(self._store)))
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
