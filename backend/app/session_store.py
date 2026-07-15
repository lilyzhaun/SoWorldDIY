from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Protocol

from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


class SessionRedisClient(Protocol):
    """Sync Redis surface used by session storage."""

    def get(self, name: str) -> str | bytes | None: ...

    def setex(self, name: str, time: int, value: str) -> object: ...

    def delete(self, *names: str) -> int: ...


def _bind_session_redis_client(client: object) -> SessionRedisClient:
    """Adapt a redis-like client to the sync session Protocol.

    redis-py stubs type many commands as ``Awaitable[T] | T``. Binding through
    ``getattr`` plus narrow runtime checks keeps store code on concrete sync
    return types while remaining compatible with ``redis.Redis`` and test fakes.
    """
    methods = {name: getattr(client, name) for name in ("get", "setex", "delete")}
    get = methods["get"]
    setex = methods["setex"]
    delete = methods["delete"]

    class _BoundSessionRedisClient:
        def get(self, name: str) -> str | bytes | None:
            raw = get(name)
            if raw is None or isinstance(raw, (str, bytes)):
                return raw
            raise TypeError(f"redis GET returned unexpected type {type(raw)!r}")

        def setex(self, name: str, time: int, value: str) -> object:
            return setex(name, time, value)

        def delete(self, *names: str) -> int:
            result = delete(*names)
            if isinstance(result, bool):
                return int(result)
            if isinstance(result, int):
                return result
            raise TypeError(f"redis DELETE returned unexpected type {type(result)!r}")

    return _BoundSessionRedisClient()


@dataclass
class SessionContext:
    sid: str
    data: dict


class RedisSessionStore:
    def __init__(
        self,
        redis_client: object,
        key_prefix: str,
        lifetime_seconds: int,
        sid_prefix: str,
    ) -> None:
        self.redis_client = _bind_session_redis_client(redis_client)
        self.key_prefix = key_prefix
        self.lifetime_seconds = lifetime_seconds
        self.sid_prefix = sid_prefix

    def new_sid(self) -> str:
        return f"{self.sid_prefix}{uuid.uuid4().hex}"

    def create(self, data: dict) -> SessionContext:
        sid = self.new_sid()
        self.save(sid, data)
        return SessionContext(sid=sid, data=data)

    def load(self, sid: str) -> dict | None:
        try:
            raw = self.redis_client.get(self._key(sid))
        except RedisError as exc:
            logger.error(
                "Redis session load failed operation=session_load error_class=%s",
                type(exc).__name__,
            )
            return None
        if not raw:
            return None
        try:
            data = json.loads(raw)
        except json.JSONDecodeError:
            return None
        return data if isinstance(data, dict) else None

    def save(self, sid: str, data: dict) -> None:
        try:
            self.redis_client.setex(
                self._key(sid),
                self.lifetime_seconds,
                json.dumps(data, ensure_ascii=False),
            )
        except RedisError as exc:
            logger.error(
                "Redis session save failed operation=session_save error_class=%s",
                type(exc).__name__,
            )
            raise RuntimeError("Redis session save failed") from exc

    def delete(self, sid: str) -> None:
        try:
            self.redis_client.delete(self._key(sid))
        except RedisError as exc:
            logger.error(
                "Redis session delete failed operation=session_delete error_class=%s",
                type(exc).__name__,
            )
            raise RuntimeError("Redis session delete failed") from exc

    def _key(self, sid: str) -> str:
        return f"{self.key_prefix}{sid}"
