from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass
from typing import Protocol

from redis.exceptions import RedisError

logger = logging.getLogger(__name__)

# All writers must use CAS; do not run the previous SETEX-only app concurrently.
_CREATE_SCRIPT = """
return redis.call('SET', KEYS[1], ARGV[1], 'EX', ARGV[2], 'NX') and 1 or 0
"""
_SAVE_SCRIPT = """
local raw = redis.call('GET', KEYS[1])
if not raw then return 0 end
local ok, current = pcall(cjson.decode, raw)
if not ok or type(current) ~= 'table' then return 0 end
if (current['_revision'] or 0) ~= tonumber(ARGV[1]) then return 0 end
redis.call('SETEX', KEYS[1], ARGV[3], ARGV[2])
return 1
"""
_ROTATE_SCRIPT = """
local raw = redis.call('GET', KEYS[1])
if not raw then return 0 end
local ok, current = pcall(cjson.decode, raw)
if not ok or type(current) ~= 'table' then return 0 end
if (current['_revision'] or 0) ~= tonumber(ARGV[1]) then return 0 end
if redis.call('EXISTS', KEYS[2]) == 1 then return 0 end
redis.call('SETEX', KEYS[2], ARGV[3], ARGV[2])
redis.call('DEL', KEYS[1])
return 1
"""


class SessionConflictError(RuntimeError):
    """A revoked or newer session must never be overwritten by a stale snapshot."""


class SessionRedisClient(Protocol):
    """Sync Redis surface used by session storage."""

    def get(self, name: str) -> str | bytes | None: ...

    def delete(self, *names: str) -> int: ...

    def eval(self, script: str, numkeys: int, *args: str) -> int: ...


def _bind_session_redis_client(client: object) -> SessionRedisClient:
    """Adapt a redis-like client to the sync session Protocol.

    redis-py stubs type many commands as ``Awaitable[T] | T``. Binding through
    ``getattr`` plus narrow runtime checks keeps store code on concrete sync
    return types while remaining compatible with ``redis.Redis`` and test fakes.
    """
    methods = {name: getattr(client, name) for name in ("get", "delete", "eval")}
    get = methods["get"]
    delete = methods["delete"]
    eval_script = methods["eval"]

    class _BoundSessionRedisClient:
        def get(self, name: str) -> str | bytes | None:
            raw = get(name)
            if raw is None or isinstance(raw, (str, bytes)):
                return raw
            raise TypeError(f"redis GET returned unexpected type {type(raw)!r}")

        def delete(self, *names: str) -> int:
            result = delete(*names)
            if isinstance(result, bool):
                return int(result)
            if isinstance(result, int):
                return result
            raise TypeError(f"redis DELETE returned unexpected type {type(result)!r}")

        def eval(self, script: str, numkeys: int, *args: str) -> int:
            result = eval_script(script, numkeys, *args)
            if isinstance(result, int):
                return result
            raise TypeError("redis session script returned a non-integer")

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
        payload = dict(data, _revision=0)
        if not self._write(
            _CREATE_SCRIPT,
            [self._key(sid)],
            json.dumps(payload, ensure_ascii=False),
            str(self._ttl(payload)),
        ):
            raise SessionConflictError("Session creation conflict")
        return SessionContext(sid=sid, data=payload)

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
        if not isinstance(data, dict):
            return None
        revision = data.get("_revision", 0)
        if not isinstance(revision, int) or revision < 0:
            return None
        return data

    def save(self, sid: str, data: dict) -> None:
        revision = data.get("_revision", 0)
        payload = dict(data, _revision=revision + 1)
        if not self._write(
            _SAVE_SCRIPT,
            [self._key(sid)],
            str(revision),
            json.dumps(payload, ensure_ascii=False),
            str(self._ttl(payload)),
        ):
            raise SessionConflictError("Session was revoked or changed")
        data["_revision"] = revision + 1

    def rotate(self, sid: str, data: dict) -> SessionContext:
        new_sid = self.new_sid()
        payload = dict(data, _revision=0)
        if not self._write(
            _ROTATE_SCRIPT,
            [self._key(sid), self._key(new_sid)],
            str(data.get("_revision", 0)),
            json.dumps(payload, ensure_ascii=False),
            str(self._ttl(payload)),
        ):
            raise SessionConflictError("Session was revoked or changed")
        return SessionContext(new_sid, payload)

    def _write(self, script: str, keys: list[str], *args: str) -> int:
        try:
            return self.redis_client.eval(script, len(keys), *keys, *args)
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

    def _ttl(self, data: dict) -> int:
        return (
            self.lifetime_seconds
            if data.get("accounts")
            else min(900, self.lifetime_seconds)
        )
