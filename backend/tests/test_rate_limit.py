"""Unit tests for rate limiting and trusted-proxy client IP resolution."""

from __future__ import annotations

from app.client_ip import parse_trusted_proxy_ips, resolve_client_ip
from app.rate_limit import (
    DEFAULT_CHECK_USER_IP_LIMIT,
    DEFAULT_LOGIN_FAIL_ID_LIMIT,
    DEFAULT_LOGIN_IP_LIMIT,
    DEFAULT_SEND_OTP_ID_LIMIT,
    DEFAULT_SEND_OTP_IP_LIMIT,
    RATE_LIMIT_PREFIX,
    RateLimitConfig,
    RateLimiter,
    load_rate_limit_config_from_env,
)


class FakeRateRedis:
    def __init__(self, *, fail: bool = False) -> None:
        self.data: dict[str, int] = {}
        self.ttls: dict[str, int] = {}
        self.fail = fail
        self.deleted: list[str] = []

    def eval(self, script: str, numkeys: int, *keys_and_args: object) -> object:
        if self.fail:
            raise ConnectionError("redis down")
        key = str(keys_and_args[0])
        window = int(str(keys_and_args[1]))
        self.data[key] = self.data.get(key, 0) + 1
        if self.data[key] == 1:
            self.ttls[key] = window
        return [self.data[key], self.ttls.get(key, window)]

    def delete(self, *names: str) -> int:
        if self.fail:
            raise ConnectionError("redis down")
        n = 0
        for name in names:
            self.deleted.append(str(name))
            if name in self.data:
                del self.data[name]
                self.ttls.pop(name, None)
                n += 1
        return n

    def get(self, name: str) -> object:
        if self.fail:
            raise ConnectionError("redis down")
        if name not in self.data:
            return None
        return str(self.data[name])

    def ttl(self, name: str) -> object:
        if self.fail:
            raise ConnectionError("redis down")
        if name not in self.data:
            return -2
        return self.ttls.get(name, -1)


def test_resolve_client_ip_uses_peer_when_untrusted() -> None:
    ip = resolve_client_ip(
        peer="203.0.113.9",
        x_forwarded_for="198.51.100.1",
        trusted_proxies=parse_trusted_proxy_ips(None),
    )
    assert ip == "203.0.113.9"


def test_resolve_client_ip_trusts_xff_from_loopback() -> None:
    ip = resolve_client_ip(
        peer="127.0.0.1",
        x_forwarded_for="198.51.100.7, 10.0.0.1",
        trusted_proxies=parse_trusted_proxy_ips(None),
    )
    assert ip == "198.51.100.7"


def test_resolve_client_ip_ignores_spoofed_xff_from_untrusted_peer() -> None:
    ip = resolve_client_ip(
        peer="203.0.113.50",
        x_forwarded_for="1.2.3.4",
        trusted_proxies=parse_trusted_proxy_ips("127.0.0.1,::1"),
    )
    assert ip == "203.0.113.50"


def test_check_user_ip_threshold_and_retry_after() -> None:
    redis = FakeRateRedis()
    limiter = RateLimiter(
        redis, RateLimitConfig(check_user_ip_limit=3, check_user_ip_window=100)
    )
    assert limiter.check_user_ip("1.1.1.1").allowed is True
    assert limiter.check_user_ip("1.1.1.1").allowed is True
    assert limiter.check_user_ip("1.1.1.1").allowed is True
    blocked = limiter.check_user_ip("1.1.1.1")
    assert blocked.allowed is False
    assert blocked.retry_after == 100
    assert any(k.startswith(RATE_LIMIT_PREFIX) for k in redis.data)


def test_send_otp_identifier_and_ip_limits() -> None:
    redis = FakeRateRedis()
    limiter = RateLimiter(
        redis,
        RateLimitConfig(
            send_otp_id_limit=2,
            send_otp_id_window=50,
            send_otp_ip_limit=3,
            send_otp_ip_window=80,
        ),
    )
    assert limiter.send_otp(ip="9.9.9.9", identifier="A@B.com").allowed is True
    assert limiter.send_otp(ip="9.9.9.9", identifier="a@b.com").allowed is True
    blocked_id = limiter.send_otp(ip="9.9.9.9", identifier="a@b.com")
    assert blocked_id.allowed is False
    # Different identifier still subject to IP limit
    assert limiter.send_otp(ip="9.9.9.9", identifier="other@x.com").allowed is True
    blocked_ip = limiter.send_otp(ip="9.9.9.9", identifier="third@x.com")
    assert blocked_ip.allowed is False
    # Keys never contain raw identifier
    joined = " ".join(redis.data)
    assert "a@b.com" not in joined.lower()
    assert "other@x.com" not in joined


def test_login_fail_bucket_clears_on_success_only() -> None:
    redis = FakeRateRedis()
    limiter = RateLimiter(
        redis,
        RateLimitConfig(
            login_fail_id_limit=2, login_fail_id_window=30, login_ip_limit=10
        ),
    )
    assert limiter.peek_login_fail_identifier("user@x.com").allowed is True
    assert limiter.record_login_failure("user@x.com").allowed is True
    assert limiter.record_login_failure("user@x.com").allowed is True
    # count==2 already at limit; peek blocks further attempts
    assert limiter.peek_login_fail_identifier("user@x.com").allowed is False
    limiter.clear_login_fail_identifier("user@x.com")
    assert limiter.peek_login_fail_identifier("user@x.com").allowed is True


def test_login_ip_limit() -> None:
    redis = FakeRateRedis()
    limiter = RateLimiter(redis, RateLimitConfig(login_ip_limit=2, login_ip_window=15))
    assert limiter.login_ip("8.8.8.8").allowed is True
    assert limiter.login_ip("8.8.8.8").allowed is True
    blocked = limiter.login_ip("8.8.8.8")
    assert blocked.allowed is False
    assert blocked.retry_after == 15


def test_redis_failure_is_redis_error() -> None:
    redis = FakeRateRedis(fail=True)
    limiter = RateLimiter(redis)
    d = limiter.check_user_ip("1.1.1.1")
    assert d.allowed is False
    assert d.redis_error is True


def test_keys_never_include_auth_code_or_raw_identifier() -> None:
    redis = FakeRateRedis()
    limiter = RateLimiter(redis)
    limiter.send_otp(ip="10.0.0.1", identifier="secret-user@example.com")
    limiter.record_login_failure("secret-user@example.com")
    for key in redis.data:
        assert key.startswith(RATE_LIMIT_PREFIX)
        assert "secret-user" not in key
        assert "auth_code" not in key
        assert "AUTH" not in key


def test_load_rate_limit_config_from_env_overrides() -> None:
    env = {
        "RATE_LIMIT_CHECK_USER_IP": "7",
        "RATE_LIMIT_LOGIN_IP": "4",
    }
    cfg = load_rate_limit_config_from_env(env.get)
    assert cfg.check_user_ip_limit == 7
    assert cfg.login_ip_limit == 4
    assert cfg.send_otp_id_limit == DEFAULT_SEND_OTP_ID_LIMIT


def test_default_limits_match_plan() -> None:
    cfg = RateLimitConfig()
    assert cfg.check_user_ip_limit == DEFAULT_CHECK_USER_IP_LIMIT == 30
    assert cfg.send_otp_id_limit == DEFAULT_SEND_OTP_ID_LIMIT == 3
    assert cfg.send_otp_ip_limit == DEFAULT_SEND_OTP_IP_LIMIT == 10
    assert cfg.login_ip_limit == DEFAULT_LOGIN_IP_LIMIT == 10
    assert cfg.login_fail_id_limit == DEFAULT_LOGIN_FAIL_ID_LIMIT == 5
