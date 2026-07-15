from __future__ import annotations

import json
import logging
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any, Protocol

from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class AuthCodeRedisClient(Protocol):
    """Sync Redis surface used by auth-code storage."""

    def exists(self, *names: str) -> int | bool: ...

    def hset(
        self,
        name: str,
        key: str | None = None,
        value: str | None = None,
        mapping: Mapping[str, object] | None = None,
    ) -> object: ...

    def delete(self, *names: str) -> int: ...

    def scan_iter(self, match: str | None = None) -> Iterable[object]: ...

    def hgetall(self, name: str) -> dict[str, str]: ...

    def eval(self, script: str, numkeys: int, *keys_and_args: str) -> object: ...


def _bind_auth_code_redis_client(client: object) -> AuthCodeRedisClient:
    """Adapt a redis-like client to the sync auth-code Protocol.

    redis-py stubs type many commands as ``Awaitable[T] | T``. Binding through
    ``getattr`` plus narrow runtime checks keeps store code on concrete sync
    return types while remaining compatible with ``redis.Redis`` and test fakes.
    """
    methods = {
        name: getattr(client, name)
        for name in ("exists", "hset", "delete", "scan_iter", "hgetall", "eval")
    }
    exists = methods["exists"]
    hset = methods["hset"]
    delete = methods["delete"]
    scan_iter = methods["scan_iter"]
    hgetall = methods["hgetall"]
    eval_script = methods["eval"]

    class _BoundAuthCodeRedisClient:
        def exists(self, *names: str) -> int | bool:
            result = exists(*names)
            if isinstance(result, bool):
                return result
            if isinstance(result, int):
                return result
            raise TypeError(f"redis EXISTS returned unexpected type {type(result)!r}")

        def hset(
            self,
            name: str,
            key: str | None = None,
            value: str | None = None,
            mapping: Mapping[str, object] | None = None,
        ) -> object:
            if mapping is not None:
                return hset(name, mapping=dict(mapping))
            return hset(name, key, value)

        def delete(self, *names: str) -> int:
            result = delete(*names)
            if isinstance(result, bool):
                return int(result)
            if isinstance(result, int):
                return result
            raise TypeError(f"redis DELETE returned unexpected type {type(result)!r}")

        def scan_iter(self, match: str | None = None) -> Iterable[object]:
            if match is None:
                return scan_iter()
            return scan_iter(match)

        def hgetall(self, name: str) -> dict[str, str]:
            result = hgetall(name)
            if not isinstance(result, dict):
                raise TypeError(
                    f"redis HGETALL returned unexpected type {type(result)!r}"
                )
            return {str(field): str(value) for field, value in result.items()}

        def eval(self, script: str, numkeys: int, *keys_and_args: str) -> object:
            return eval_script(script, numkeys, *keys_and_args)

    return _BoundAuthCodeRedisClient()


class AuthCodeStore:
    def __init__(
        self, redis_client: object, seed_file: Path, key_prefix: str = "auth_code:"
    ) -> None:
        self.redis_client = _bind_auth_code_redis_client(redis_client)
        self.seed_file = seed_file
        self.key_prefix = key_prefix

    def seed_from_file(self) -> int:
        if not self.seed_file.exists():
            return 0
        try:
            data = json.loads(self.seed_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(
                "Failed to load auth code seed file operation=auth_code_seed error_class=%s",
                type(exc).__name__,
            )
            return 0
        if not isinstance(data, dict):
            return 0

        imported = 0
        for code, entry in data.items():
            if not isinstance(code, str) or not isinstance(entry, dict):
                continue
            try:
                usage_limit = int(entry.get("usage_limit", 0))
                times_used = int(entry.get("times_used", 0))
            except (TypeError, ValueError):
                continue
            if usage_limit <= 0:
                continue
            key = self._key(code)
            try:
                if self.redis_client.exists(key):
                    continue
                self.redis_client.hset(
                    key, mapping={"usage_limit": usage_limit, "times_used": times_used}
                )
                imported += 1
            except RedisError as exc:
                logger.warning(
                    "Failed to seed auth code operation=auth_code_seed error_class=%s",
                    type(exc).__name__,
                )
        return imported

    def verify(self, auth_code: str | None, consume: bool = False) -> tuple[bool, str]:
        if not auth_code:
            return False, "请输入鉴权码"
        try:
            return self._verify_redis(auth_code, consume)
        except RedisError as exc:
            logger.error(
                "Redis auth code verification failed operation=auth_code_verify error_class=%s",
                type(exc).__name__,
            )
            return False, "鉴权服务暂不可用"

    def create(self, auth_code: str, usage_limit: int, times_used: int = 0) -> None:
        if not auth_code:
            raise ValueError("auth_code is required")
        if usage_limit <= 0:
            raise ValueError("usage_limit must be positive")
        if times_used < 0:
            raise ValueError("times_used cannot be negative")
        self.redis_client.hset(
            self._key(auth_code),
            mapping={"usage_limit": usage_limit, "times_used": times_used},
        )

    def revoke(self, auth_code: str) -> bool:
        return bool(self.redis_client.delete(self._key(auth_code)))

    def list_codes(self) -> list[dict[str, Any]]:
        result: list[dict[str, Any]] = []
        for raw_key in self.redis_client.scan_iter(f"{self.key_prefix}*"):
            key = str(raw_key)
            code = key.removeprefix(self.key_prefix)
            entry = self.redis_client.hgetall(key)
            result.append(
                {
                    "code": code,
                    "usage_limit": int(entry.get("usage_limit", 0)),
                    "times_used": int(entry.get("times_used", 0)),
                }
            )
        return sorted(result, key=lambda item: item["code"])

    def _verify_redis(self, auth_code: str, consume: bool) -> tuple[bool, str]:
        key = self._key(auth_code)
        if consume:
            script = """
            local key = KEYS[1]
            if redis.call('EXISTS', key) == 0 then
                return {-1, 0, 0}
            end
            local usage_limit = tonumber(redis.call('HGET', key, 'usage_limit') or '0')
            local times_used = tonumber(redis.call('HGET', key, 'times_used') or '0')
            if times_used >= usage_limit then
                return {0, usage_limit, times_used}
            end
            local next_used = redis.call('HINCRBY', key, 'times_used', 1)
            return {1, usage_limit, next_used}
            """
            result = self.redis_client.eval(script, 1, key)
            if not isinstance(result, (list, tuple)) or len(result) < 1:
                raise RedisError("auth code eval returned unexpected payload")
            status = int(str(result[0]))
            if status == -1:
                return False, "无效鉴权码"
            if status == 0:
                return False, "鉴权码已用完"
            return True, "OK"

        entry = self.redis_client.hgetall(key)
        if not entry:
            return False, "无效鉴权码"
        usage_limit = int(entry.get("usage_limit", 0))
        times_used = int(entry.get("times_used", 0))
        if times_used >= usage_limit:
            return False, "鉴权码已用完"
        return True, "OK"

    def _key(self, auth_code: str) -> str:
        return f"{self.key_prefix}{auth_code}"
