"""Sync Redis Protocol adapter for auth-code storage."""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import Protocol


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


def bind_auth_code_redis_client(client: object) -> AuthCodeRedisClient:
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
