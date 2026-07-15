from __future__ import annotations

import hashlib
import hmac
import logging
from io import StringIO
from pathlib import Path
from typing import Any

import pytest
from redis.exceptions import RedisError

from app.auth_code_keys import (
    MIN_HMAC_KEY_BYTES,
    V2_DIGEST_HEX_LEN,
    AuthCodeKeyMode,
    fingerprint_from_digest,
    is_legacy_redis_key,
    is_reserved_v2_shaped_code,
    is_v2_redis_key,
    parse_auth_code_hmac_key,
    parse_auth_code_key_mode,
    v2_redis_key,
)
from app.auth_codes import AuthCodeStore

HMAC_SECRET = b"x" * MIN_HMAC_KEY_BYTES
SENTINEL_CODE = "CODE_SENTINEL"


class FakeRedis:
    def __init__(self) -> None:
        self.data: dict[str, dict[str, str]] = {}

    def exists(self, key: str) -> bool:
        return key in self.data

    def hset(
        self,
        name: str,
        key: str | None = None,
        value: str | None = None,
        mapping: dict[str, object] | None = None,
    ) -> None:
        if mapping is not None:
            self.data[name] = {str(k): str(v) for k, v in mapping.items()}
            return
        if key is None:
            raise TypeError("hset requires key or mapping")
        entry = self.data.setdefault(name, {})
        entry[str(key)] = str(value)

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.data.get(key, {}))

    def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                removed += 1
        return removed

    def scan_iter(self, match: str | None = None) -> list[str]:
        if match is None:
            return list(self.data)
        prefix = match.removesuffix("*")
        return [key for key in self.data if key.startswith(prefix)]

    def eval(self, _: str, __: int, key: str) -> tuple[int, int, int]:
        if key not in self.data:
            return (-1, 0, 0)
        entry = self.data[key]
        usage_limit = int(entry.get("usage_limit", 0))
        times_used = int(entry.get("times_used", 0))
        if times_used >= usage_limit:
            return (0, usage_limit, times_used)
        entry["times_used"] = str(times_used + 1)
        return (1, usage_limit, times_used + 1)


def make_store(
    redis_client: Any,
    *,
    mode: AuthCodeKeyMode = AuthCodeKeyMode.LEGACY,
    hmac_key: bytes | None = None,
    seed_file: Path | None = None,
) -> AuthCodeStore:
    return AuthCodeStore(
        redis_client,
        seed_file=seed_file or Path("/tmp/missing-auth-codes.json"),
        key_mode=mode,
        hmac_key=hmac_key,
    )


def expected_v2_key(code: str, key: bytes = HMAC_SECRET) -> str:
    return v2_redis_key(key, code)


def expected_fingerprint(code: str, key: bytes = HMAC_SECRET) -> str:
    digest = hmac.new(key, code.encode("utf-8"), hashlib.sha256).hexdigest()
    return fingerprint_from_digest(digest)


# --- mode / secret parsing -------------------------------------------------


def test_parse_auth_code_key_mode_accepts_canonical_values() -> None:
    assert parse_auth_code_key_mode("legacy") is AuthCodeKeyMode.LEGACY
    assert parse_auth_code_key_mode("dual") is AuthCodeKeyMode.DUAL
    assert parse_auth_code_key_mode("hmac") is AuthCodeKeyMode.HMAC


def test_parse_auth_code_key_mode_rejects_unknown() -> None:
    with pytest.raises(ValueError, match="AUTH_CODE_KEY_MODE"):
        parse_auth_code_key_mode("sha256")


def test_parse_auth_code_hmac_key_requires_min_length() -> None:
    with pytest.raises(ValueError, match="AUTH_CODE_HMAC_KEY"):
        parse_auth_code_hmac_key("short")
    with pytest.raises(ValueError, match="AUTH_CODE_HMAC_KEY"):
        parse_auth_code_hmac_key(None)
    with pytest.raises(ValueError, match="AUTH_CODE_HMAC_KEY"):
        parse_auth_code_hmac_key("")
    secret = "a" * MIN_HMAC_KEY_BYTES
    assert parse_auth_code_hmac_key(secret) == secret.encode("utf-8")


def test_hmac_key_error_message_does_not_echo_secret() -> None:
    secret = "UNIQUE_SECRET_FRAGMENT"
    assert len(secret.encode("utf-8")) < MIN_HMAC_KEY_BYTES
    with pytest.raises(ValueError) as exc_info:
        parse_auth_code_hmac_key(secret)
    assert secret not in str(exc_info.value)
    assert "UNIQUE_SECRET_FRAGMENT" not in str(exc_info.value)


def test_store_rejects_missing_hmac_key_in_dual_and_hmac() -> None:
    for mode in (AuthCodeKeyMode.DUAL, AuthCodeKeyMode.HMAC):
        with pytest.raises(ValueError, match="AUTH_CODE_HMAC_KEY"):
            make_store(FakeRedis(), mode=mode, hmac_key=None)


def test_store_rejects_short_hmac_key_in_dual() -> None:
    with pytest.raises(ValueError, match="AUTH_CODE_HMAC_KEY"):
        make_store(FakeRedis(), mode=AuthCodeKeyMode.DUAL, hmac_key=b"too-short")


# --- legacy mode (default migration behavior) -----------------------------


def test_legacy_create_verify_consume_and_revoke() -> None:
    redis_client = FakeRedis()
    store = make_store(redis_client)

    store.create("CODE", usage_limit=1)
    assert "auth_code:CODE" in redis_client.data
    assert store.verify("CODE") == (True, "OK")
    assert store.verify("CODE", consume=True) == (True, "OK")
    assert store.verify("CODE") == (False, "鉴权码已用完")
    assert store.revoke("CODE") is True
    assert store.verify("CODE") == (False, "无效鉴权码")


def test_legacy_list_codes_shows_plaintext_code() -> None:
    redis_client = FakeRedis()
    store = make_store(redis_client)
    store.create("B", usage_limit=2, times_used=1)
    store.create("A", usage_limit=3)
    assert store.list_codes() == [
        {"code": "A", "usage_limit": 3, "times_used": 0},
        {"code": "B", "usage_limit": 2, "times_used": 1},
    ]


def test_legacy_mode_does_not_require_hmac_key() -> None:
    store = make_store(FakeRedis(), mode=AuthCodeKeyMode.LEGACY, hmac_key=None)
    store.create("LEGACY_ONLY", usage_limit=1)
    assert store.verify("LEGACY_ONLY") == (True, "OK")


# --- deterministic v2 key material ----------------------------------------


def test_v2_key_is_deterministic_hmac_sha256_hex() -> None:
    code = SENTINEL_CODE
    expected_digest = hmac.new(
        HMAC_SECRET, code.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert expected_digest == expected_digest.lower()
    key = expected_v2_key(code)
    assert key == f"auth_code:v2:{expected_digest}"
    assert SENTINEL_CODE not in key
    assert "CODE" not in key


# --- hmac mode ------------------------------------------------------------


def test_hmac_create_writes_v2_key_without_code() -> None:
    redis_client = FakeRedis()
    store = make_store(redis_client, mode=AuthCodeKeyMode.HMAC, hmac_key=HMAC_SECRET)
    store.create(SENTINEL_CODE, usage_limit=2)
    keys = list(redis_client.data)
    assert keys == [expected_v2_key(SENTINEL_CODE)]
    for key in keys:
        assert SENTINEL_CODE not in key
    assert store.verify(SENTINEL_CODE) == (True, "OK")
    assert store.verify(SENTINEL_CODE, consume=True) == (True, "OK")
    assert redis_client.data[expected_v2_key(SENTINEL_CODE)]["times_used"] == "1"


def test_hmac_refuses_legacy_only_data() -> None:
    redis_client = FakeRedis()
    redis_client.data["auth_code:LEGACY_ONLY"] = {
        "usage_limit": "5",
        "times_used": "0",
    }
    store = make_store(redis_client, mode=AuthCodeKeyMode.HMAC, hmac_key=HMAC_SECRET)
    assert store.verify("LEGACY_ONLY") == (False, "无效鉴权码")
    assert store.verify("LEGACY_ONLY", consume=True) == (False, "无效鉴权码")


def test_hmac_list_returns_fingerprint_never_code() -> None:
    redis_client = FakeRedis()
    store = make_store(redis_client, mode=AuthCodeKeyMode.HMAC, hmac_key=HMAC_SECRET)
    store.create(SENTINEL_CODE, usage_limit=3, times_used=1)
    listed = store.list_codes()
    assert listed == [
        {
            "fingerprint": expected_fingerprint(SENTINEL_CODE),
            "usage_limit": 3,
            "times_used": 1,
        }
    ]
    serialized = str(listed)
    assert SENTINEL_CODE not in serialized
    assert "code" not in listed[0]


def test_hmac_revoke_removes_v2() -> None:
    redis_client = FakeRedis()
    store = make_store(redis_client, mode=AuthCodeKeyMode.HMAC, hmac_key=HMAC_SECRET)
    store.create("R1", usage_limit=1)
    assert store.revoke("R1") is True
    assert redis_client.data == {}
    assert store.revoke("R1") is False


# --- dual mode ------------------------------------------------------------


def test_dual_writes_v2_only() -> None:
    redis_client = FakeRedis()
    store = make_store(redis_client, mode=AuthCodeKeyMode.DUAL, hmac_key=HMAC_SECRET)
    store.create(SENTINEL_CODE, usage_limit=4)
    assert list(redis_client.data) == [expected_v2_key(SENTINEL_CODE)]
    assert f"auth_code:{SENTINEL_CODE}" not in redis_client.data


def test_dual_reads_legacy_fallback() -> None:
    redis_client = FakeRedis()
    redis_client.data[f"auth_code:{SENTINEL_CODE}"] = {
        "usage_limit": "2",
        "times_used": "0",
    }
    store = make_store(redis_client, mode=AuthCodeKeyMode.DUAL, hmac_key=HMAC_SECRET)
    assert store.verify(SENTINEL_CODE) == (True, "OK")
    assert store.verify(SENTINEL_CODE, consume=True) == (True, "OK")
    assert redis_client.data[f"auth_code:{SENTINEL_CODE}"]["times_used"] == "1"


def test_dual_prefers_v2_over_legacy() -> None:
    redis_client = FakeRedis()
    code = "DUAL_BOTH"
    redis_client.data[f"auth_code:{code}"] = {
        "usage_limit": "9",
        "times_used": "8",
    }
    redis_client.data[expected_v2_key(code)] = {
        "usage_limit": "3",
        "times_used": "0",
    }
    store = make_store(redis_client, mode=AuthCodeKeyMode.DUAL, hmac_key=HMAC_SECRET)
    assert store.verify(code) == (True, "OK")
    assert store.verify(code, consume=True) == (True, "OK")
    assert redis_client.data[expected_v2_key(code)]["times_used"] == "1"
    assert redis_client.data[f"auth_code:{code}"]["times_used"] == "8"


def test_dual_revoke_deletes_both_versions() -> None:
    redis_client = FakeRedis()
    code = "REV_BOTH"
    redis_client.data[f"auth_code:{code}"] = {
        "usage_limit": "1",
        "times_used": "0",
    }
    redis_client.data[expected_v2_key(code)] = {
        "usage_limit": "1",
        "times_used": "0",
    }
    store = make_store(redis_client, mode=AuthCodeKeyMode.DUAL, hmac_key=HMAC_SECRET)
    assert store.revoke(code) is True
    assert redis_client.data == {}


def test_dual_list_dedupes_legacy_and_v2_as_fingerprint() -> None:
    redis_client = FakeRedis()
    code = "DEDUP"
    redis_client.data[f"auth_code:{code}"] = {
        "usage_limit": "5",
        "times_used": "1",
    }
    redis_client.data[expected_v2_key(code)] = {
        "usage_limit": "5",
        "times_used": "2",
    }
    store = make_store(redis_client, mode=AuthCodeKeyMode.DUAL, hmac_key=HMAC_SECRET)
    listed = store.list_codes()
    assert listed == [
        {
            "fingerprint": expected_fingerprint(code),
            "usage_limit": 5,
            "times_used": 2,
        }
    ]
    assert code not in str(listed)


def test_dual_list_legacy_only_as_fingerprint() -> None:
    redis_client = FakeRedis()
    code = "LEG_ONLY"
    redis_client.data[f"auth_code:{code}"] = {
        "usage_limit": "2",
        "times_used": "0",
    }
    store = make_store(redis_client, mode=AuthCodeKeyMode.DUAL, hmac_key=HMAC_SECRET)
    listed = store.list_codes()
    assert listed == [
        {
            "fingerprint": expected_fingerprint(code),
            "usage_limit": 2,
            "times_used": 0,
        }
    ]
    assert code not in str(listed)


# --- seed / redis errors / empty verify -----------------------------------


def test_seed_from_file_writes_according_to_mode(tmp_path: Path) -> None:
    seed = tmp_path / "auth_codes.json"
    seed.write_text(
        '{"SEED1": {"usage_limit": 3, "times_used": 1}}',
        encoding="utf-8",
    )
    legacy_redis = FakeRedis()
    legacy_store = make_store(legacy_redis, seed_file=seed)
    assert legacy_store.seed_from_file() == 1
    assert "auth_code:SEED1" in legacy_redis.data

    hmac_redis = FakeRedis()
    hmac_store = make_store(
        hmac_redis,
        mode=AuthCodeKeyMode.HMAC,
        hmac_key=HMAC_SECRET,
        seed_file=seed,
    )
    assert hmac_store.seed_from_file() == 1
    assert expected_v2_key("SEED1") in hmac_redis.data
    assert "auth_code:SEED1" not in hmac_redis.data


def test_seed_skips_existing_key(tmp_path: Path) -> None:
    seed = tmp_path / "auth_codes.json"
    seed.write_text(
        '{"SEED1": {"usage_limit": 3, "times_used": 0}}',
        encoding="utf-8",
    )
    redis_client = FakeRedis()
    store = make_store(
        redis_client,
        mode=AuthCodeKeyMode.DUAL,
        hmac_key=HMAC_SECRET,
        seed_file=seed,
    )
    redis_client.data["auth_code:SEED1"] = {
        "usage_limit": "9",
        "times_used": "9",
    }
    assert store.seed_from_file() == 0
    assert expected_v2_key("SEED1") not in redis_client.data


def test_verify_empty_code_message() -> None:
    store = make_store(FakeRedis())
    assert store.verify(None) == (False, "请输入鉴权码")
    assert store.verify("") == (False, "请输入鉴权码")


def test_verify_redis_error_returns_unavailable() -> None:
    class Boom:
        def exists(self, *names: str) -> int:
            raise RedisError("boom")

        def hset(self, *a: object, **k: object) -> None:
            raise RedisError("boom")

        def delete(self, *names: str) -> int:
            raise RedisError("boom")

        def scan_iter(self, match: str | None = None):
            raise RedisError("boom")

        def hgetall(self, name: str) -> dict[str, str]:
            raise RedisError("boom")

        def eval(self, *a: object, **k: object) -> object:
            raise RedisError("boom")

    store = make_store(Boom(), mode=AuthCodeKeyMode.LEGACY)
    ok, msg = store.verify("X")
    assert ok is False
    assert msg == "鉴权服务暂不可用"


def test_create_validation_errors() -> None:
    store = make_store(FakeRedis())
    with pytest.raises(ValueError, match="auth_code is required"):
        store.create("", usage_limit=1)
    with pytest.raises(ValueError, match="usage_limit"):
        store.create("C", usage_limit=0)
    with pytest.raises(ValueError, match="times_used"):
        store.create("C", usage_limit=1, times_used=-1)


def test_settings_default_legacy_without_hmac_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-value-32chars!!")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("AUTH_CODE_KEY_MODE", "legacy")
    monkeypatch.setenv("AUTH_CODE_HMAC_KEY", "")
    from app.config import load_settings

    settings = load_settings()
    assert settings.auth_code_key_mode is AuthCodeKeyMode.LEGACY
    assert settings.auth_code_hmac_key is None


def test_settings_dual_requires_hmac_key(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-value-32chars!!")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("AUTH_CODE_KEY_MODE", "dual")
    monkeypatch.setenv("AUTH_CODE_HMAC_KEY", "")
    from app.config import load_settings

    with pytest.raises(RuntimeError, match="AUTH_CODE_HMAC_KEY"):
        load_settings()


def test_settings_hmac_mode_loads_key(monkeypatch: pytest.MonkeyPatch) -> None:
    secret = "k" * MIN_HMAC_KEY_BYTES
    monkeypatch.setenv("SESSION_SECRET", "test-session-secret-value-32chars!!")
    monkeypatch.setenv("COOKIE_SECURE", "false")
    monkeypatch.setenv("AUTH_CODE_KEY_MODE", "hmac")
    monkeypatch.setenv("AUTH_CODE_HMAC_KEY", secret)
    from app.config import load_settings

    settings = load_settings()
    assert settings.auth_code_key_mode is AuthCodeKeyMode.HMAC
    assert settings.auth_code_hmac_key == secret.encode("utf-8")


def test_logging_never_includes_hmac_key_or_code(tmp_path: Path) -> None:
    from app.auth_codes import AuthCodeStore

    class Boom:
        def exists(self, *names: str) -> int:
            raise RedisError(SENTINEL_CODE)

        def hset(self, *a: object, **k: object) -> None:
            raise RedisError(SENTINEL_CODE)

        def delete(self, *names: str) -> int:
            return 0

        def scan_iter(self, match: str | None = None):
            return []

        def hgetall(self, name: str) -> dict[str, str]:
            raise RedisError(SENTINEL_CODE)

        def eval(self, *a: object, **k: object) -> object:
            raise RedisError(SENTINEL_CODE)

    seed = tmp_path / "auth_codes.json"
    seed.write_text(
        f'{{"{SENTINEL_CODE}": {{"usage_limit": 1, "times_used": 0}}}}',
        encoding="utf-8",
    )
    store = AuthCodeStore(
        Boom(),
        seed_file=seed,
        key_mode=AuthCodeKeyMode.HMAC,
        hmac_key=HMAC_SECRET,
    )
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    logger = logging.getLogger("app.auth_codes")
    logger.addHandler(handler)
    try:
        store.seed_from_file()
        ok, _msg = store.verify(SENTINEL_CODE)
        assert ok is False
    finally:
        logger.removeHandler(handler)
    log_text = buf.getvalue()
    assert SENTINEL_CODE not in log_text
    assert HMAC_SECRET.decode() not in log_text
    assert "error_class=RedisError" in log_text


# --- v2 key shape hardening -------------------------------------------------


def test_is_v2_redis_key_requires_exact_64_lowercase_hex() -> None:
    valid = "auth_code:v2:" + ("ab" * 32)
    assert is_v2_redis_key(valid) is True
    assert is_legacy_redis_key("auth_code:v2:NOTHEX_SUFFIX") is True
    assert is_v2_redis_key("auth_code:v2:NOTHEX_SUFFIX") is False
    assert is_v2_redis_key("auth_code:v2:" + ("AB" * 32)) is False
    assert is_v2_redis_key("auth_code:v2:" + ("ab" * 31)) is False


def test_reserved_v2_shaped_code_detection() -> None:
    reserved = "v2:" + ("cd" * 32)
    assert is_reserved_v2_shaped_code(reserved) is True
    assert is_reserved_v2_shaped_code("v2:NOTHEX") is False
    assert is_reserved_v2_shaped_code("plain") is False


def test_create_rejects_reserved_v2_shaped_code() -> None:
    store = make_store(FakeRedis())
    reserved = "v2:" + ("ef" * 32)
    with pytest.raises(ValueError, match="reserved v2 key shape"):
        store.create(reserved, usage_limit=1)


def test_legacy_list_includes_malformed_v2_prefix_as_code() -> None:
    redis_client = FakeRedis()
    code = "v2:NOTAVALIDHEXDIGEST"
    redis_client.data[f"auth_code:{code}"] = {
        "usage_limit": "2",
        "times_used": "1",
    }
    store = make_store(redis_client)
    listed = store.list_codes()
    assert listed == [
        {"code": code, "usage_limit": 2, "times_used": 1},
    ]


def test_dual_list_malformed_v2_prefix_uses_hmac_fingerprint_not_suffix() -> None:
    redis_client = FakeRedis()
    code = "v2:NOTAVALIDHEXDIGEST_SENTINEL"
    redis_client.data[f"auth_code:{code}"] = {
        "usage_limit": "3",
        "times_used": "0",
    }
    store = make_store(redis_client, mode=AuthCodeKeyMode.DUAL, hmac_key=HMAC_SECRET)
    listed = store.list_codes()
    assert listed == [
        {
            "fingerprint": expected_fingerprint(code),
            "usage_limit": 3,
            "times_used": 0,
        }
    ]
    assert code not in str(listed)
    assert "NOTAVALIDHEX" not in str(listed)


def test_dual_list_keeps_distinct_digests_sharing_presentation_fingerprint() -> None:
    redis_client = FakeRedis()
    shared = "a" * 12
    digest_a = shared + ("0" * (V2_DIGEST_HEX_LEN - 12))
    digest_b = shared + ("1" * (V2_DIGEST_HEX_LEN - 12))
    redis_client.data[f"auth_code:v2:{digest_a}"] = {
        "usage_limit": "4",
        "times_used": "1",
    }
    redis_client.data[f"auth_code:v2:{digest_b}"] = {
        "usage_limit": "5",
        "times_used": "2",
    }
    store = make_store(redis_client, mode=AuthCodeKeyMode.DUAL, hmac_key=HMAC_SECRET)
    listed = store.list_codes()
    assert len(listed) == 2
    assert {item["fingerprint"] for item in listed} == {shared}
    assert {item["usage_limit"] for item in listed} == {4, 5}
    assert {item["times_used"] for item in listed} == {1, 2}


def test_dual_list_does_not_hide_legacy_when_presentation_fingerprint_collides() -> (
    None
):
    redis_client = FakeRedis()
    code = "LEGACY_COLLIDE"
    fp = expected_fingerprint(code)
    foreign_digest = fp + ("9" * (V2_DIGEST_HEX_LEN - 12))
    redis_client.data[f"auth_code:v2:{foreign_digest}"] = {
        "usage_limit": "9",
        "times_used": "9",
    }
    redis_client.data[f"auth_code:{code}"] = {
        "usage_limit": "2",
        "times_used": "1",
    }
    store = make_store(redis_client, mode=AuthCodeKeyMode.DUAL, hmac_key=HMAC_SECRET)
    listed = store.list_codes()
    assert len(listed) == 2
    by_usage = {item["usage_limit"]: item for item in listed}
    assert by_usage[9]["fingerprint"] == fp
    assert by_usage[2]["fingerprint"] == fp
    assert by_usage[2]["times_used"] == 1
    assert code not in str(listed)


def test_hmac_list_ignores_malformed_v2_prefix_keys() -> None:
    redis_client = FakeRedis()
    redis_client.data["auth_code:v2:NOTHEX"] = {
        "usage_limit": "1",
        "times_used": "0",
    }
    redis_client.data[expected_v2_key("GOOD")] = {
        "usage_limit": "2",
        "times_used": "0",
    }
    store = make_store(redis_client, mode=AuthCodeKeyMode.HMAC, hmac_key=HMAC_SECRET)
    listed = store.list_codes()
    assert listed == [
        {
            "fingerprint": expected_fingerprint("GOOD"),
            "usage_limit": 2,
            "times_used": 0,
        }
    ]
