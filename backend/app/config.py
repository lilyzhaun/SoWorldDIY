from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .auth_code_keys import (
    AuthCodeKeyMode,
    parse_auth_code_key_mode,
    require_hmac_key_for_mode,
)
from .client_ip import parse_trusted_proxy_ips
from .rate_limit import RateLimitConfig, load_rate_limit_config_from_env

ENV_FILE = Path(__file__).resolve().parent.parent / ".env"


def _load_env_file(path: Path = ENV_FILE) -> None:
    if not path.exists():
        return

    for line in path.read_text(encoding="utf-8").splitlines():
        entry = line.strip()
        if not entry or entry.startswith("#") or "=" not in entry:
            continue
        name, value = entry.split("=", 1)
        name = name.strip()
        if not name or name in os.environ:
            continue
        os.environ[name] = value.strip().strip('"').strip("'")


def _get_required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


def _get_required_bool_env(name: str) -> bool:
    raw = os.environ.get(name)
    if raw is None or not str(raw).strip():
        raise RuntimeError(f"{name} is required")
    value = str(raw).strip().lower()
    if value == "true":
        return True
    if value == "false":
        return False
    raise RuntimeError(f"{name} must be true or false")


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    session_secret: str
    redis_url: str
    redis_session_prefix: str
    proxy_url: str
    password_encryption_key: str
    cookie_secure: bool
    auth_code_key_mode: AuthCodeKeyMode
    auth_code_hmac_key: bytes | None
    trusted_proxy_ips: frozenset[str]
    rate_limit: RateLimitConfig
    metrics_secret: str

    @property
    def proxies(self) -> dict[str, str] | None:
        if not self.proxy_url:
            return None
        return {"http": self.proxy_url, "https": self.proxy_url}


def load_settings() -> Settings:
    _load_env_file()

    session_secret = _get_required_env("SESSION_SECRET")
    password_encryption_key = os.environ.get("PASSWORD_ENCRYPTION_KEY", "").strip()
    if not password_encryption_key:
        password_encryption_key = session_secret

    try:
        auth_code_key_mode = parse_auth_code_key_mode(
            os.environ.get("AUTH_CODE_KEY_MODE")
        )
        auth_code_hmac_key = require_hmac_key_for_mode(
            auth_code_key_mode, os.environ.get("AUTH_CODE_HMAC_KEY")
        )
    except ValueError as exc:
        raise RuntimeError(str(exc)) from exc

    return Settings(
        base_dir=Path(__file__).resolve().parent.parent,
        session_secret=session_secret,
        redis_url=os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
        redis_session_prefix=os.environ.get("REDIS_SESSION_PREFIX", "session:"),
        proxy_url=os.environ.get("PROXY_URL", "").strip(),
        password_encryption_key=password_encryption_key,
        cookie_secure=_get_required_bool_env("COOKIE_SECURE"),
        auth_code_key_mode=auth_code_key_mode,
        auth_code_hmac_key=auth_code_hmac_key,
        trusted_proxy_ips=parse_trusted_proxy_ips(os.environ.get("TRUSTED_PROXY_IPS")),
        rate_limit=load_rate_limit_config_from_env(os.environ.get),
        metrics_secret=_get_required_env("METRICS_SECRET"),
    )
