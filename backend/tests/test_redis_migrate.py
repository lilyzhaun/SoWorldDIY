"""Tests for dedicated-Redis migration plan/apply/verify and ACL denials."""

from __future__ import annotations

import json
import os
import shutil
import socket
import subprocess
import tempfile
import time
from pathlib import Path
from typing import Any

import pytest

from app.auth_code_keys import MIN_HMAC_KEY_BYTES, v2_redis_key
from app.redis_migrate import _redact_redis_url
from app.redis_migrate import run as migrate_run
from app.redis_migrate_core import (
    apply_plan,
    build_plan,
    rollback_plan_public,
    verify_plan,
)

HMAC_SECRET = b"m" * MIN_HMAC_KEY_BYTES
SENTINEL_CODE = "MIGRATE_SENTINEL_CODE"


class FakeMigrateRedis:
    """In-memory Redis stand-in with DUMP/RESTORE and hash ops."""

    def __init__(self) -> None:
        self.strings: dict[str, bytes] = {}
        self.hashes: dict[str, dict[str, str]] = {}
        self.pttls: dict[str, int] = {}

    def scan_iter(self, match: str | None = None) -> list[str]:
        keys = set(self.strings) | set(self.hashes)
        if match is None:
            return sorted(keys)
        prefix = match.removesuffix("*")
        return sorted(k for k in keys if k.startswith(prefix))

    def pttl(self, name: str) -> int:
        if name not in self.strings and name not in self.hashes:
            return -2
        return self.pttls.get(name, -1)

    def dump(self, name: str) -> bytes | None:
        if name in self.strings:
            return b"S:" + self.strings[name]
        if name in self.hashes:
            payload = json.dumps(self.hashes[name], sort_keys=True).encode("utf-8")
            return b"H:" + payload
        return None

    def restore(
        self,
        name: str,
        ttl: int,
        value: bytes,
        *,
        replace: bool = False,
    ) -> None:
        if not replace and (name in self.strings or name in self.hashes):
            raise RuntimeError("BUSYKEY")
        if value.startswith(b"S:"):
            self.strings[name] = value[2:]
            self.hashes.pop(name, None)
        elif value.startswith(b"H:"):
            self.hashes[name] = json.loads(value[2:].decode("utf-8"))
            self.strings.pop(name, None)
        else:
            raise RuntimeError("bad dump")
        if ttl > 0:
            self.pttls[name] = ttl
        else:
            self.pttls.pop(name, None)

    def hgetall(self, name: str) -> dict[str, str]:
        return dict(self.hashes.get(name, {}))

    def hset(
        self,
        name: str,
        key: str | None = None,
        value: str | None = None,
        mapping: dict[str, object] | None = None,
    ) -> None:
        entry = self.hashes.setdefault(name, {})
        if mapping is not None:
            entry.update({str(k): str(v) for k, v in mapping.items()})
            return
        if key is None:
            raise TypeError("hset requires key or mapping")
        entry[str(key)] = str(value)

    def exists(self, *names: str) -> int:
        return sum(1 for n in names if n in self.strings or n in self.hashes)

    def get(self, name: str) -> bytes | None:
        return self.strings.get(name)

    def pexpire(self, name: str, ttl: int) -> None:
        self.pttls[name] = ttl

    def setex(self, name: str, seconds: int, value: bytes | str) -> None:
        raw = value if isinstance(value, bytes) else str(value).encode("utf-8")
        self.strings[name] = raw
        self.pttls[name] = int(seconds) * 1000


def test_build_plan_counts_prefixes_and_maps_auth_to_v2() -> None:
    src = FakeMigrateRedis()
    src.setex("session:abc", 120, b'{"u":1}')
    src.setex("cache:plans", 60, b"[]")
    src.hset(
        f"auth_code:{SENTINEL_CODE}",
        mapping={"usage_limit": "5", "times_used": "2"},
    )
    v2 = v2_redis_key(HMAC_SECRET, "ALREADY")
    src.hset(v2, mapping={"usage_limit": "1", "times_used": "0"})

    plan = build_plan(src, hmac_key=HMAC_SECRET)
    public = plan.as_public_dict()
    assert public["session_count"] == 1
    assert public["cache_count"] == 1
    assert public["auth_legacy_count"] == 1
    assert public["auth_v2_count"] == 1
    assert SENTINEL_CODE not in json.dumps(public)
    assert f"auth_code:{SENTINEL_CODE}" not in json.dumps(public)

    legacy_items = [i for i in plan.items if i.kind == "auth_legacy"]
    assert len(legacy_items) == 1
    assert legacy_items[0].dest_key == v2_redis_key(HMAC_SECRET, SENTINEL_CODE)


def test_apply_and_verify_preserve_ttl_and_auth_counters() -> None:
    src = FakeMigrateRedis()
    dest = FakeMigrateRedis()
    src.setex("session:s1", 300, b"sess-payload")
    src.setex("cache:c1", 90, b"cache-payload")
    src.hset(
        f"auth_code:{SENTINEL_CODE}",
        mapping={"usage_limit": "9", "times_used": "3"},
    )

    plan = build_plan(src, hmac_key=HMAC_SECRET)
    copied = apply_plan(src, dest, plan)
    assert copied == {"session": 1, "cache": 1, "auth_legacy": 1, "auth_v2": 0}

    result = verify_plan(src, dest, plan)
    assert result["ok"] is True
    assert dest.strings["session:s1"] == b"sess-payload"
    assert dest.strings["cache:c1"] == b"cache-payload"
    dest_auth = dest.hashes[v2_redis_key(HMAC_SECRET, SENTINEL_CODE)]
    assert dest_auth == {"usage_limit": "9", "times_used": "3"}
    assert SENTINEL_CODE not in dest.hashes


def test_plan_does_not_include_unrelated_prefixes() -> None:
    src = FakeMigrateRedis()
    src.setex("other:secret", 10, b"nope")
    src.setex("session:ok", 10, b"yes")
    plan = build_plan(src, hmac_key=HMAC_SECRET)
    assert plan.session_count == 1
    assert all(not i.source_key.startswith("other:") for i in plan.items)


def test_verify_rejects_corrupted_session_and_apply_preserves_destination():
    src, dst = FakeMigrateRedis(), FakeMigrateRedis()
    src.setex("session:test", 60, b"correct")
    plan = build_plan(src, hmac_key=HMAC_SECRET)
    apply_plan(src, dst, plan)
    dst.strings["session:test"] = b"corrupted"
    assert verify_plan(src, dst, plan)["ok"] is False
    with pytest.raises(RuntimeError, match="BUSYKEY"):
        apply_plan(src, dst, plan)
    assert dst.get("session:test") == b"corrupted"


def test_migration_refuses_other_databases():
    from app.redis_migrate import _connect

    with pytest.raises(SystemExit, match="DB 0"):
        _connect("redis://127.0.0.1:1/15")
    with pytest.raises(SystemExit, match="DB 0"):
        _connect("redis://127.0.0.1:1/0?db=15")


def test_rollback_plan_public_has_atomic_url_and_mode_steps() -> None:
    payload = rollback_plan_public()
    text = json.dumps(payload)
    assert "REDIS_URL" in text or "redis://" in text
    assert "AUTH_CODE_KEY_MODE" in text
    assert "DB 15" in text or "db15" in text.lower()
    assert "FLUSHALL" not in text or "Never FLUSH" in text


def test_redact_redis_url_strips_password() -> None:
    redacted = _redact_redis_url("redis://app:s3cret@127.0.0.1:6380/0")
    assert "s3cret" not in redacted
    assert "6380" in redacted


def test_cli_plan_requires_hmac_and_never_echoes_secret() -> None:
    secret = "UNIQUE_MIGRATE_SECRET_FRAG"
    with pytest.raises(SystemExit) as exc:
        migrate_run(
            [
                "plan",
                "--source-url",
                "redis://127.0.0.1:1/0",
                "--hmac-key",
                secret,
            ]
        )
    message = str(exc.value)
    assert "AUTH_CODE_HMAC_KEY" in message
    assert secret not in message


def _free_port() -> int:
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(("127.0.0.1", 0))
        return int(sock.getsockname()[1])


def _wait_ping(port: int, password: str | None = None, user: str | None = None) -> None:
    import redis as redis_lib

    kwargs: dict[str, Any] = {"host": "127.0.0.1", "port": port, "db": 0}
    if user and password:
        kwargs["username"] = user
        kwargs["password"] = password
    elif password:
        kwargs["password"] = password
    deadline = time.time() + 8
    last: Exception | None = None
    while time.time() < deadline:
        try:
            client = redis_lib.Redis(**kwargs)
            assert client.ping() is True
            client.close()
            return
        except Exception as exc:  # noqa: BLE001 - wait loop
            last = exc
            time.sleep(0.1)
    raise RuntimeError(f"redis not ready on {port}: {last}")


@pytest.fixture(scope="module")
def disposable_redis_pair() -> Any:
    """Two temporary Redis 8 instances for migration integration tests."""
    if shutil.which("redis-server") is None:
        pytest.skip("redis-server not installed")

    src_port = _free_port()
    dst_port = _free_port()
    tmp = Path(tempfile.mkdtemp(prefix="3hk-redis-migrate-"))
    procs: list[subprocess.Popen[str]] = []
    acl_password = "test-acl-password-not-for-prod"
    acl_path = tmp / "users.acl"
    acl_path.write_text(
        "\n".join(
            [
                "user default on nopass ~* &* +@all",
                (
                    f"user 3hk-app on >{acl_password} "
                    "~session:* ~cache:* ~auth_code:v2:* ~ratelimit:* &* "
                    "+@read +@write +@connection +@scripting +@transaction "
                    "-@dangerous -config -acl -slowlog"
                ),
                "",
            ]
        ),
        encoding="utf-8",
    )

    def start(port: int, name: str, with_acl: bool) -> subprocess.Popen[str]:
        conf = tmp / f"{name}.conf"
        lines = [
            f"port {port}",
            "bind 127.0.0.1",
            "protected-mode yes",
            'save ""',
            "appendonly no",
            f"dir {tmp}",
            f"dbfilename {name}.rdb",
            "databases 16",
        ]
        if with_acl:
            lines.append(f"aclfile {acl_path}")
        conf.write_text("\n".join(lines) + "\n", encoding="utf-8")
        proc = subprocess.Popen(
            ["redis-server", str(conf)],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
            text=True,
        )
        procs.append(proc)
        return proc

    start(src_port, "src", with_acl=False)
    start(dst_port, "dst", with_acl=True)
    try:
        _wait_ping(src_port)
        _wait_ping(dst_port)
        yield {
            "src_port": src_port,
            "dst_port": dst_port,
            "acl_password": acl_password,
            "tmp": tmp,
        }
    finally:
        for proc in procs:
            proc.terminate()
            try:
                proc.wait(timeout=3)
            except subprocess.TimeoutExpired:
                proc.kill()
        shutil.rmtree(tmp, ignore_errors=True)


def test_integration_migrate_preserves_ttl_and_leaves_db15(
    disposable_redis_pair: dict[str, Any],
) -> None:
    import redis as redis_lib

    src_port = disposable_redis_pair["src_port"]
    dst_port = disposable_redis_pair["dst_port"]
    src = redis_lib.Redis(host="127.0.0.1", port=src_port, db=0, decode_responses=False)
    src15 = redis_lib.Redis(
        host="127.0.0.1", port=src_port, db=15, decode_responses=False
    )
    # Seed DB15 sentinel — must remain untouched by migration tooling.
    src15.set("db15:sentinel", b"do-not-touch")
    db15_before = src15.dbsize()

    src.setex(b"session:live", 120, b'{"sid":1}')
    src.setex(b"cache:live", 45, b"cached")
    src.hset(
        f"auth_code:{SENTINEL_CODE}".encode(),
        mapping={b"usage_limit": b"4", b"times_used": b"1"},
    )
    # Unrelated key must not be copied
    src.set(b"other:skip", b"x")

    env = {
        **os.environ,
        "AUTH_CODE_HMAC_KEY": HMAC_SECRET.decode("utf-8"),
    }
    src_url = f"redis://127.0.0.1:{src_port}/0"
    dst_url = f"redis://127.0.0.1:{dst_port}/0"

    from io import StringIO

    out = StringIO()
    rc = migrate_run(
        [
            "plan",
            "--source-url",
            src_url,
            "--dest-url",
            dst_url,
            "--hmac-key",
            env["AUTH_CODE_HMAC_KEY"],
        ],
        out=out,
    )
    assert rc == 0
    plan_json = json.loads(out.getvalue())
    assert plan_json["session_count"] == 1
    assert plan_json["cache_count"] == 1
    assert plan_json["auth_legacy_count"] == 1
    assert SENTINEL_CODE not in out.getvalue()

    out2 = StringIO()
    rc = migrate_run(
        [
            "apply",
            "--source-url",
            src_url,
            "--dest-url",
            dst_url,
            "--hmac-key",
            env["AUTH_CODE_HMAC_KEY"],
        ],
        out=out2,
    )
    assert rc == 0
    assert "status" in out2.getvalue()

    out3 = StringIO()
    rc = migrate_run(
        [
            "verify",
            "--source-url",
            src_url,
            "--dest-url",
            dst_url,
            "--hmac-key",
            env["AUTH_CODE_HMAC_KEY"],
        ],
        out=out3,
    )
    assert rc == 0
    assert json.loads(out3.getvalue())["ok"] is True

    dest = redis_lib.Redis(
        host="127.0.0.1", port=dst_port, db=0, decode_responses=False
    )
    assert dest.get(b"session:live") == b'{"sid":1}'
    assert dest.get(b"cache:live") == b"cached"
    assert dest.exists(b"other:skip") == 0
    v2_key = v2_redis_key(HMAC_SECRET, SENTINEL_CODE).encode()
    fields = dest.hgetall(v2_key)
    assert fields[b"usage_limit"] == b"4"
    assert fields[b"times_used"] == b"1"
    assert src15.get(b"db15:sentinel") == b"do-not-touch"
    assert src15.dbsize() == db15_before


def test_integration_acl_denies_other_keys_and_config(
    disposable_redis_pair: dict[str, Any],
) -> None:
    import redis as redis_lib
    from redis.exceptions import ResponseError

    dst_port = disposable_redis_pair["dst_port"]
    password = disposable_redis_pair["acl_password"]
    # Seed with default/admin (nopass default still on for bootstrap)
    admin = redis_lib.Redis(
        host="127.0.0.1", port=dst_port, db=0, decode_responses=True
    )
    admin.set("session:ok", "1")
    admin.set("other:secret", "leak")

    app = redis_lib.Redis(
        host="127.0.0.1",
        port=dst_port,
        db=0,
        username="3hk-app",
        password=password,
        decode_responses=True,
    )
    assert app.get("session:ok") == "1"
    with pytest.raises(ResponseError, match="(?i)noperm|no permission"):
        app.get("other:secret")
    with pytest.raises(ResponseError, match="(?i)noperm|no permission"):
        app.execute_command("CONFIG", "GET", "dir")
    with pytest.raises(ResponseError, match="(?i)noperm|no permission"):
        app.execute_command("ACL", "LIST")
    # Ensure denial did not delete other key
    assert admin.get("other:secret") == "leak"
