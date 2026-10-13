"""Redis fixed-window rate limits (``ratelimit:`` keys; hashed identifiers only)."""

from __future__ import annotations

import hashlib
from collections.abc import Callable
from dataclasses import dataclass
from typing import Final, Protocol

RATE_LIMIT_PREFIX: Final[str] = "ratelimit:"
DEFAULT_CHECK_USER_IP_LIMIT = 30
DEFAULT_CHECK_USER_IP_WINDOW = 300
DEFAULT_SEND_OTP_ID_LIMIT = 3
DEFAULT_SEND_OTP_ID_WINDOW = 600
DEFAULT_SEND_OTP_IP_LIMIT = 10
DEFAULT_SEND_OTP_IP_WINDOW = 3600
DEFAULT_LOGIN_IP_LIMIT = 10
DEFAULT_LOGIN_IP_WINDOW = 900
DEFAULT_LOGIN_FAIL_ID_LIMIT = 5
DEFAULT_LOGIN_FAIL_ID_WINDOW = 900

_LUA_HIT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], ARGV[1])
end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""


class RateLimitRedis(Protocol):
    def eval(self, script: str, numkeys: int, *keys_and_args: str) -> object: ...
    def delete(self, *names: str) -> object: ...
    def get(self, name: str) -> object: ...
    def ttl(self, name: str) -> object: ...


@dataclass(frozen=True, slots=True)
class RateLimitConfig:
    check_user_ip_limit: int = DEFAULT_CHECK_USER_IP_LIMIT
    check_user_ip_window: int = DEFAULT_CHECK_USER_IP_WINDOW
    send_otp_id_limit: int = DEFAULT_SEND_OTP_ID_LIMIT
    send_otp_id_window: int = DEFAULT_SEND_OTP_ID_WINDOW
    send_otp_ip_limit: int = DEFAULT_SEND_OTP_IP_LIMIT
    send_otp_ip_window: int = DEFAULT_SEND_OTP_IP_WINDOW
    login_ip_limit: int = DEFAULT_LOGIN_IP_LIMIT
    login_ip_window: int = DEFAULT_LOGIN_IP_WINDOW
    login_fail_id_limit: int = DEFAULT_LOGIN_FAIL_ID_LIMIT
    login_fail_id_window: int = DEFAULT_LOGIN_FAIL_ID_WINDOW


@dataclass(frozen=True, slots=True)
class RateLimitDecision:
    allowed: bool
    retry_after: int = 0
    redis_error: bool = False


def _hash_identifier(identifier: str) -> str:
    return hashlib.sha256(identifier.strip().lower().encode("utf-8")).hexdigest()


def _bucket_key(scope: str, dimension: str, value: str) -> str:
    return f"{RATE_LIMIT_PREFIX}{scope}:{dimension}:{value}"


def bind_rate_limit_redis(client: object) -> RateLimitRedis:
    """Adapt redis-py client to RateLimitRedis Protocol."""
    eval_script = getattr(client, "eval")  # noqa: B009
    delete_fn = getattr(client, "delete")  # noqa: B009
    get_fn = getattr(client, "get")  # noqa: B009
    ttl_fn = getattr(client, "ttl")  # noqa: B009

    class _Bound:
        def eval(self, script: str, numkeys: int, *keys_and_args: str) -> object:
            return eval_script(script, numkeys, *keys_and_args)

        def delete(self, *names: str) -> object:
            return delete_fn(*names)

        def get(self, name: str) -> object:
            return get_fn(name)

        def ttl(self, name: str) -> object:
            return ttl_fn(name)

    return _Bound()


class RateLimiter:
    """Fixed-window counters stored under ``ratelimit:*``."""

    def __init__(
        self, redis_client: object, config: RateLimitConfig | None = None
    ) -> None:
        self._redis = bind_rate_limit_redis(redis_client)
        self._config = config or RateLimitConfig()

    def _hit(self, key: str, limit: int, window_seconds: int) -> RateLimitDecision:
        try:
            raw = self._redis.eval(_LUA_HIT, 1, key, str(window_seconds))
        except Exception:
            return RateLimitDecision(allowed=False, retry_after=0, redis_error=True)
        count, ttl = _parse_eval_pair(raw)
        if ttl < 0:
            ttl = window_seconds
        if count > limit:
            return RateLimitDecision(
                allowed=False, retry_after=max(1, int(ttl)), redis_error=False
            )
        return RateLimitDecision(allowed=True, retry_after=0, redis_error=False)

    def check_user_ip(self, ip: str) -> RateLimitDecision:
        cfg = self._config
        return self._hit(
            _bucket_key("check_user", "ip", ip),
            cfg.check_user_ip_limit,
            cfg.check_user_ip_window,
        )

    def session_create_ip(self, ip: str) -> RateLimitDecision:
        cfg = self._config
        return self._hit(
            _bucket_key("session_create", "ip", ip),
            cfg.check_user_ip_limit,
            cfg.check_user_ip_window,
        )

    def send_otp(self, *, ip: str, identifier: str) -> RateLimitDecision:
        ip_decision = self.send_otp_ip(ip)
        if ip_decision.redis_error or not ip_decision.allowed:
            return ip_decision
        return self.send_otp_identifier(identifier)

    def send_otp_ip(self, ip: str) -> RateLimitDecision:
        cfg = self._config
        return self._hit(
            _bucket_key("send_otp", "ip", ip),
            cfg.send_otp_ip_limit,
            cfg.send_otp_ip_window,
        )

    def send_otp_identifier(self, identifier: str) -> RateLimitDecision:
        cfg = self._config
        id_hash = _hash_identifier(identifier)
        return self._hit(
            _bucket_key("send_otp", "id", id_hash),
            cfg.send_otp_id_limit,
            cfg.send_otp_id_window,
        )

    def login_ip(self, ip: str) -> RateLimitDecision:
        cfg = self._config
        return self._hit(
            _bucket_key("login", "ip", ip),
            cfg.login_ip_limit,
            cfg.login_ip_window,
        )

    def peek_login_fail_identifier(self, identifier: str) -> RateLimitDecision:
        """Reject if fail bucket already at/over limit (no INCR)."""
        cfg = self._config
        key = _bucket_key("login", "fail_id", _hash_identifier(identifier))
        try:
            raw = self._redis.get(key)
            ttl_raw = self._redis.ttl(key)
        except Exception:
            return RateLimitDecision(allowed=False, retry_after=0, redis_error=True)
        count = _as_int(raw, default=0)
        ttl = _as_int(ttl_raw, default=-1)
        if count >= cfg.login_fail_id_limit:
            retry = max(1, ttl if ttl > 0 else cfg.login_fail_id_window)
            return RateLimitDecision(
                allowed=False, retry_after=retry, redis_error=False
            )
        return RateLimitDecision(allowed=True, retry_after=0, redis_error=False)

    def record_login_failure(self, identifier: str) -> RateLimitDecision:
        """INCR fail bucket after auth failure."""
        cfg = self._config
        return self._hit(
            _bucket_key("login", "fail_id", _hash_identifier(identifier)),
            cfg.login_fail_id_limit,
            cfg.login_fail_id_window,
        )

    def clear_login_fail_identifier(self, identifier: str) -> None:
        key = _bucket_key("login", "fail_id", _hash_identifier(identifier))
        try:
            self._redis.delete(key)
        except Exception:
            return


def _as_int(raw: object, *, default: int = 0) -> int:
    if raw is None:
        return default
    if isinstance(raw, bool):
        return int(raw)
    if isinstance(raw, int):
        return raw
    if isinstance(raw, (bytes, bytearray)):
        text = raw.decode("utf-8", errors="replace").strip()
        return int(text) if text else default
    if isinstance(raw, str):
        text = raw.strip()
        return int(text) if text else default
    try:
        return int(str(raw))
    except (TypeError, ValueError):
        return default


def _parse_eval_pair(raw: object) -> tuple[int, int]:
    if isinstance(raw, (list, tuple)) and len(raw) >= 2:
        return _as_int(raw[0]), _as_int(raw[1], default=-1)
    raise TypeError(f"unexpected redis eval result type {type(raw)!r}")


def load_rate_limit_config_from_env(
    getenv: Callable[[str], str | None],
) -> RateLimitConfig:
    """Env overrides; invalid values fall back to defaults."""

    def _int(name: str, default: int) -> int:
        raw = getenv(name)
        if raw is None or not str(raw).strip():
            return default
        try:
            value = int(str(raw).strip())
        except ValueError:
            return default
        return value if value > 0 else default

    return RateLimitConfig(
        check_user_ip_limit=_int(
            "RATE_LIMIT_CHECK_USER_IP", DEFAULT_CHECK_USER_IP_LIMIT
        ),
        check_user_ip_window=_int(
            "RATE_LIMIT_CHECK_USER_WINDOW", DEFAULT_CHECK_USER_IP_WINDOW
        ),
        send_otp_id_limit=_int("RATE_LIMIT_SEND_OTP_ID", DEFAULT_SEND_OTP_ID_LIMIT),
        send_otp_id_window=_int(
            "RATE_LIMIT_SEND_OTP_ID_WINDOW", DEFAULT_SEND_OTP_ID_WINDOW
        ),
        send_otp_ip_limit=_int("RATE_LIMIT_SEND_OTP_IP", DEFAULT_SEND_OTP_IP_LIMIT),
        send_otp_ip_window=_int(
            "RATE_LIMIT_SEND_OTP_IP_WINDOW", DEFAULT_SEND_OTP_IP_WINDOW
        ),
        login_ip_limit=_int("RATE_LIMIT_LOGIN_IP", DEFAULT_LOGIN_IP_LIMIT),
        login_ip_window=_int("RATE_LIMIT_LOGIN_IP_WINDOW", DEFAULT_LOGIN_IP_WINDOW),
        login_fail_id_limit=_int(
            "RATE_LIMIT_LOGIN_FAIL_ID", DEFAULT_LOGIN_FAIL_ID_LIMIT
        ),
        login_fail_id_window=_int(
            "RATE_LIMIT_LOGIN_FAIL_ID_WINDOW", DEFAULT_LOGIN_FAIL_ID_WINDOW
        ),
    )
