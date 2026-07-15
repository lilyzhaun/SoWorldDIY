"""CLI coverage for auth_cli create/list/revoke/seed paths."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.auth_cli import build_parser, main
from app.auth_code_keys import MIN_HMAC_KEY_BYTES, AuthCodeKeyMode
from app.auth_codes import AuthCodeStore
from app.config import Settings


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
        entry = self.data.setdefault(name, {})
        entry[str(key)] = str(value)

    def hgetall(self, key: str) -> dict[str, str]:
        return dict(self.data.get(key, {}))

    def delete(self, *keys: str) -> int:
        n = 0
        for key in keys:
            if key in self.data:
                del self.data[key]
                n += 1
        return n

    def scan_iter(self, match: str | None = None) -> list[str]:
        if match is None:
            return list(self.data)
        prefix = match.removesuffix("*")
        return [k for k in self.data if k.startswith(prefix)]

    def eval(self, _: str, __: int, key: str) -> tuple[int, int, int]:
        if key not in self.data:
            return (-1, 0, 0)
        entry = self.data[key]
        limit = int(entry.get("usage_limit", 0))
        used = int(entry.get("times_used", 0))
        if used >= limit:
            return (0, limit, used)
        entry["times_used"] = str(used + 1)
        return (1, limit, used + 1)


def _settings(
    tmp_path: Path, mode: AuthCodeKeyMode = AuthCodeKeyMode.LEGACY
) -> Settings:
    hmac_key = (
        (b"k" * MIN_HMAC_KEY_BYTES) if mode is not AuthCodeKeyMode.LEGACY else None
    )
    return Settings(
        base_dir=tmp_path,
        session_secret="s" * 32,
        redis_url="redis://127.0.0.1:6379/0",
        redis_session_prefix="session:",
        proxy_url="",
        password_encryption_key="p" * 32,
        cookie_secure=False,
        auth_code_key_mode=mode,
        auth_code_hmac_key=hmac_key,
        trusted_proxy_ips=frozenset({"127.0.0.1"}),
        rate_limit=__import__(
            "app.rate_limit", fromlist=["RateLimitConfig"]
        ).RateLimitConfig(),
        metrics_secret="m" * 32,
    )


def test_build_parser_requires_command() -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([])


def test_main_create_list_revoke_legacy(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    redis = FakeRedis()
    settings = _settings(tmp_path, AuthCodeKeyMode.LEGACY)

    def fake_load() -> Settings:
        return settings

    def fake_store(s: Settings) -> AuthCodeStore:
        return AuthCodeStore(
            redis,
            seed_file=tmp_path / "auth_codes.json",
            key_mode=s.auth_code_key_mode,
            hmac_key=s.auth_code_hmac_key,
        )

    monkeypatch.setattr("app.auth_cli.load_settings", fake_load)
    monkeypatch.setattr("app.auth_cli.build_store", fake_store)
    monkeypatch.setattr(
        "sys.argv",
        ["auth_cli", "create", "CODE1", "--limit", "3", "--used", "1"],
    )
    main()
    out = capsys.readouterr().out
    assert json.loads(out)["code"] == "CODE1"

    monkeypatch.setattr("sys.argv", ["auth_cli", "list"])
    main()
    listed = json.loads(capsys.readouterr().out)
    assert any(item.get("code") == "CODE1" for item in listed)

    monkeypatch.setattr("sys.argv", ["auth_cli", "revoke", "CODE1"])
    main()
    assert json.loads(capsys.readouterr().out)["deleted"] is True


def test_main_create_hmac_fingerprint_only(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    redis = FakeRedis()
    settings = _settings(tmp_path, AuthCodeKeyMode.HMAC)

    monkeypatch.setattr("app.auth_cli.load_settings", lambda: settings)
    monkeypatch.setattr(
        "app.auth_cli.build_store",
        lambda s: AuthCodeStore(
            redis,
            seed_file=tmp_path / "missing.json",
            key_mode=s.auth_code_key_mode,
            hmac_key=s.auth_code_hmac_key,
        ),
    )
    monkeypatch.setattr("sys.argv", ["auth_cli", "create", "SECRET", "--limit", "2"])
    main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert "fingerprint" in payload
    assert "code" not in payload
    assert "SECRET" not in json.dumps(payload)


def test_main_seed(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path, capsys: pytest.CaptureFixture[str]
) -> None:
    redis = FakeRedis()
    seed = tmp_path / "auth_codes.json"
    seed.write_text(
        json.dumps({"SEED": {"usage_limit": 5, "times_used": 0}}), encoding="utf-8"
    )
    settings = _settings(tmp_path, AuthCodeKeyMode.LEGACY)
    monkeypatch.setattr("app.auth_cli.load_settings", lambda: settings)
    monkeypatch.setattr(
        "app.auth_cli.build_store",
        lambda s: AuthCodeStore(
            redis,
            seed_file=seed,
            key_mode=s.auth_code_key_mode,
            hmac_key=s.auth_code_hmac_key,
        ),
    )
    monkeypatch.setattr("sys.argv", ["auth_cli", "seed"])
    main()
    payload = json.loads(capsys.readouterr().out)
    assert payload["status"] == "ok"
    assert payload["imported"] >= 1
