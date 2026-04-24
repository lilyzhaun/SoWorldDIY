from __future__ import annotations

import json
import logging
import uuid
from dataclasses import dataclass

import redis
from redis.exceptions import RedisError

logger = logging.getLogger(__name__)


@dataclass
class SessionContext:
    sid: str
    data: dict


class RedisSessionStore:
    def __init__(
        self,
        redis_client: redis.Redis,
        key_prefix: str,
        lifetime_seconds: int,
        sid_prefix: str,
    ) -> None:
        self.redis_client = redis_client
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
            logger.error("Redis session load failed for %s: %s", sid, exc)
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
            logger.error("Redis session save failed for %s: %s", sid, exc)
            raise RuntimeError(f"Redis session save failed: {exc}") from exc

    def delete(self, sid: str) -> None:
        try:
            self.redis_client.delete(self._key(sid))
        except RedisError as exc:
            logger.error("Redis session delete failed for %s: %s", sid, exc)
            raise RuntimeError(f"Redis session delete failed: {exc}") from exc

    def _key(self, sid: str) -> str:
        return f"{self.key_prefix}{sid}"
