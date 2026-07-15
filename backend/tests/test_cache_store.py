from __future__ import annotations

import time

from app.cache_store import MemoryCache


def test_memory_cache_copies_values() -> None:
    cache = MemoryCache(default_timeout=60)
    value = {"items": [1]}
    cache.set("key", value)
    value["items"].append(2)

    cached = cache.get("key")
    assert cached == {"items": [1]}
    cached["items"].append(3)
    assert cache.get("key") == {"items": [1]}


def test_memory_cache_delete() -> None:
    cache = MemoryCache(default_timeout=60)
    cache.set("key", "value")
    cache.delete("key")
    assert cache.get("key") is None


def test_memory_cache_expired_entry_returns_none() -> None:
    cache = MemoryCache(default_timeout=1)
    cache.set("k", {"v": 1}, timeout=0)
    time.sleep(0.01)
    assert cache.get("k") is None
    assert cache.get("missing") is None
