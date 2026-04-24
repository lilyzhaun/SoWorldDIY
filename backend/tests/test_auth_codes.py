from pathlib import Path
from typing import Any

from app.auth_codes import AuthCodeStore


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, int]] = {}

    def exists(self, key: str) -> bool:
        return key in self.data

    def hset(self, key: str, mapping: dict[str, int]) -> None:
        self.data[key] = dict(mapping)

    def hgetall(self, key: str) -> dict[str, int]:
        return dict(self.data.get(key, {}))

    def delete(self, key: str) -> int:
        existed = key in self.data
        self.data.pop(key, None)
        return int(existed)

    def scan_iter(self, pattern: str) -> list[str]:
        prefix = pattern.removesuffix("*")
        return [key for key in self.data if key.startswith(prefix)]

    def eval(self, _: str, __: int, key: str) -> tuple[int, int, int]:
        if key not in self.data:
            return (-1, 0, 0)
        entry = self.data[key]
        usage_limit = int(entry.get("usage_limit", 0))
        times_used = int(entry.get("times_used", 0))
        if times_used >= usage_limit:
            return (0, usage_limit, times_used)
        entry["times_used"] = times_used + 1
        return (1, usage_limit, entry["times_used"])


def make_store(redis_client: Any) -> AuthCodeStore:
    return AuthCodeStore(redis_client, seed_file=Path("/tmp/missing-auth-codes.json"))


def test_auth_code_create_verify_consume_and_revoke() -> None:
    redis_client = FakeRedis()
    store = make_store(redis_client)

    store.create("CODE", usage_limit=1)
    assert store.verify("CODE") == (True, "OK")
    assert store.verify("CODE", consume=True) == (True, "OK")
    assert store.verify("CODE") == (False, "鉴权码已用完")
    assert store.revoke("CODE") is True
    assert store.verify("CODE") == (False, "无效鉴权码")


def test_auth_code_list_codes() -> None:
    redis_client = FakeRedis()
    store = make_store(redis_client)
    store.create("B", usage_limit=2, times_used=1)
    store.create("A", usage_limit=3)
    assert store.list_codes() == [
        {"code": "A", "usage_limit": 3, "times_used": 0},
        {"code": "B", "usage_limit": 2, "times_used": 1},
    ]
