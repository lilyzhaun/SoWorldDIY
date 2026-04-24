from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


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


def _get_int_env(name: str, default: int) -> int:
    raw = os.environ.get(name)
    if raw is None or raw == "":
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise RuntimeError(f"{name} must be an integer") from exc


def _get_required_env(name: str) -> str:
    value = os.environ.get(name, "").strip()
    if not value:
        raise RuntimeError(f"{name} is required")
    return value


@dataclass(frozen=True)
class Settings:
    base_dir: Path
    session_secret: str
    redis_url: str
    redis_session_prefix: str
    proxy_url: str
    external_delivery_token: str
    external_delivery_target: int
    password_encryption_key: str

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

    return Settings(
        base_dir=Path(__file__).resolve().parent.parent,
        session_secret=session_secret,
        redis_url=os.environ.get("REDIS_URL", "redis://127.0.0.1:6379/0"),
        redis_session_prefix=os.environ.get("REDIS_SESSION_PREFIX", "session:"),
        proxy_url=os.environ.get("PROXY_URL", "").strip(),
        external_delivery_token=os.environ.get("external_delivery_token", ""),
        external_delivery_target=_get_int_env("external_delivery_target", 0),
        password_encryption_key=password_encryption_key,
    )
