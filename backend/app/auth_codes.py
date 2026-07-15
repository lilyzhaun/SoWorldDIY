from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import assert_never

from redis.exceptions import RedisError

from .auth_code_keys import (
    MIN_HMAC_KEY_BYTES,
    AuthCodeKeyMode,
    fingerprint_for_code,
    fingerprint_from_digest,
    is_legacy_redis_key,
    is_reserved_v2_shaped_code,
    is_v2_redis_key,
    legacy_code_from_key,
    legacy_redis_key,
    v2_digest,
    v2_digest_from_key,
    v2_redis_key,
)
from .auth_code_redis import bind_auth_code_redis_client

logger = logging.getLogger(__name__)

_CONSUME_SCRIPT = """
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


class AuthCodeStore:
    def __init__(
        self,
        redis_client: object,
        seed_file: Path,
        key_prefix: str = "auth_code:",
        *,
        key_mode: AuthCodeKeyMode = AuthCodeKeyMode.LEGACY,
        hmac_key: bytes | None = None,
    ) -> None:
        self.redis_client = bind_auth_code_redis_client(redis_client)
        self.seed_file = seed_file
        self.key_prefix = key_prefix
        self.key_mode = key_mode
        self.hmac_key = self._resolve_hmac_key(key_mode, hmac_key)

    @staticmethod
    def _resolve_hmac_key(
        key_mode: AuthCodeKeyMode, hmac_key: bytes | None
    ) -> bytes | None:
        if key_mode is AuthCodeKeyMode.LEGACY:
            return None
        if hmac_key is None or len(hmac_key) < MIN_HMAC_KEY_BYTES:
            raise ValueError(
                "AUTH_CODE_HMAC_KEY is required and must be at least "
                f"{MIN_HMAC_KEY_BYTES} bytes"
            )
        return hmac_key

    def seed_from_file(self) -> int:
        if not self.seed_file.exists():
            return 0
        try:
            data = json.loads(self.seed_file.read_text(encoding="utf-8"))
        except Exception as exc:
            logger.warning(
                "Failed to load auth code seed file operation=auth_code_seed "
                "error_class=%s",
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
            try:
                if self._any_key_exists(code):
                    continue
                self.create(code, usage_limit=usage_limit, times_used=times_used)
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
                "Redis auth code verification failed operation=auth_code_verify "
                "error_class=%s",
                type(exc).__name__,
            )
            return False, "鉴权服务暂不可用"

    def create(self, auth_code: str, usage_limit: int, times_used: int = 0) -> None:
        if not auth_code:
            raise ValueError("auth_code is required")
        if is_reserved_v2_shaped_code(auth_code):
            raise ValueError(
                "auth_code collides with the reserved v2 key shape and cannot be created"
            )
        if usage_limit <= 0:
            raise ValueError("usage_limit must be positive")
        if times_used < 0:
            raise ValueError("times_used cannot be negative")
        self.redis_client.hset(
            self._write_key(auth_code),
            mapping={"usage_limit": usage_limit, "times_used": times_used},
        )

    def revoke(self, auth_code: str) -> bool:
        keys = self._revoke_keys(auth_code)
        if not keys:
            return False
        return bool(self.redis_client.delete(*keys))

    def list_codes(self) -> list[dict[str, str | int]]:
        match self.key_mode:
            case AuthCodeKeyMode.LEGACY:
                return self._list_legacy()
            case AuthCodeKeyMode.DUAL | AuthCodeKeyMode.HMAC:
                return self._list_fingerprints()
            case unreachable:
                assert_never(unreachable)

    def fingerprint(self, auth_code: str) -> str:
        if self.hmac_key is None:
            raise ValueError("fingerprint requires AUTH_CODE_HMAC_KEY")
        return fingerprint_for_code(self.hmac_key, auth_code)

    def _write_key(self, auth_code: str) -> str:
        match self.key_mode:
            case AuthCodeKeyMode.LEGACY:
                return legacy_redis_key(auth_code, self.key_prefix)
            case AuthCodeKeyMode.DUAL | AuthCodeKeyMode.HMAC:
                assert self.hmac_key is not None
                return v2_redis_key(self.hmac_key, auth_code)
            case unreachable:
                assert_never(unreachable)

    def _locate_key(self, auth_code: str) -> str | None:
        match self.key_mode:
            case AuthCodeKeyMode.LEGACY:
                key = legacy_redis_key(auth_code, self.key_prefix)
                return key if self.redis_client.exists(key) else None
            case AuthCodeKeyMode.HMAC:
                assert self.hmac_key is not None
                key = v2_redis_key(self.hmac_key, auth_code)
                return key if self.redis_client.exists(key) else None
            case AuthCodeKeyMode.DUAL:
                assert self.hmac_key is not None
                v2_key = v2_redis_key(self.hmac_key, auth_code)
                if self.redis_client.exists(v2_key):
                    return v2_key
                legacy_key = legacy_redis_key(auth_code, self.key_prefix)
                return legacy_key if self.redis_client.exists(legacy_key) else None
            case unreachable:
                assert_never(unreachable)

    def _revoke_keys(self, auth_code: str) -> list[str]:
        match self.key_mode:
            case AuthCodeKeyMode.LEGACY:
                return [legacy_redis_key(auth_code, self.key_prefix)]
            case AuthCodeKeyMode.HMAC:
                assert self.hmac_key is not None
                return [v2_redis_key(self.hmac_key, auth_code)]
            case AuthCodeKeyMode.DUAL:
                assert self.hmac_key is not None
                return [
                    v2_redis_key(self.hmac_key, auth_code),
                    legacy_redis_key(auth_code, self.key_prefix),
                ]
            case unreachable:
                assert_never(unreachable)

    def _any_key_exists(self, auth_code: str) -> bool:
        return any(
            self.redis_client.exists(key) for key in self._revoke_keys(auth_code)
        )

    def _verify_redis(self, auth_code: str, consume: bool) -> tuple[bool, str]:
        key = self._locate_key(auth_code)
        if key is None:
            return False, "无效鉴权码"
        if consume:
            result = self.redis_client.eval(_CONSUME_SCRIPT, 1, key)
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

    def _list_legacy(self) -> list[dict[str, str | int]]:
        result: list[dict[str, str | int]] = []
        for raw_key in self.redis_client.scan_iter(f"{self.key_prefix}*"):
            key = str(raw_key)
            if not is_legacy_redis_key(key, self.key_prefix):
                continue
            entry = self.redis_client.hgetall(key)
            result.append(
                {
                    "code": legacy_code_from_key(key, self.key_prefix),
                    "usage_limit": int(entry.get("usage_limit", 0)),
                    "times_used": int(entry.get("times_used", 0)),
                }
            )
        return sorted(result, key=lambda item: str(item["code"]))

    def _list_fingerprints(self) -> list[dict[str, str | int]]:
        """List dual/hmac entries keyed by full digest; present 12-hex fingerprints.

        Identity and dedupe use the full 64-hex digest so distinct digests that
        share a presentation fingerprint never hide each other.
        """
        assert self.hmac_key is not None
        by_digest: dict[str, dict[str, str | int]] = {}
        for raw_key in self.redis_client.scan_iter(f"{self.key_prefix}*"):
            key = str(raw_key)
            if not is_v2_redis_key(key):
                continue
            digest = v2_digest_from_key(key)
            entry = self.redis_client.hgetall(key)
            by_digest[digest] = {
                "fingerprint": fingerprint_from_digest(digest),
                "usage_limit": int(entry.get("usage_limit", 0)),
                "times_used": int(entry.get("times_used", 0)),
            }
        if self.key_mode is AuthCodeKeyMode.DUAL:
            for raw_key in self.redis_client.scan_iter(f"{self.key_prefix}*"):
                key = str(raw_key)
                if not is_legacy_redis_key(key, self.key_prefix):
                    continue
                code = legacy_code_from_key(key, self.key_prefix)
                digest = v2_digest(self.hmac_key, code)
                if digest in by_digest:
                    continue
                entry = self.redis_client.hgetall(key)
                by_digest[digest] = {
                    "fingerprint": fingerprint_from_digest(digest),
                    "usage_limit": int(entry.get("usage_limit", 0)),
                    "times_used": int(entry.get("times_used", 0)),
                }
        ordered = sorted(
            by_digest.items(),
            key=lambda pair: (str(pair[1]["fingerprint"]), pair[0]),
        )
        return [row for _, row in ordered]
