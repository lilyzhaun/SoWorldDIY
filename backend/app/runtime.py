from __future__ import annotations

import threading
from collections.abc import Mapping
from datetime import timedelta
from pathlib import Path
from typing import Any, Protocol

import redis
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .auth_codes import AuthCodeStore
from .brand import SUPPORTED_BRANDS
from .cache_store import MemoryCache
from .config import load_settings
from .rate_limit import RateLimiter
from .security import (
    create_password_cipher,
)
from .security import (
    decrypt_password as decrypt_password_value,
)
from .security import (
    encrypt_password as encrypt_password_value,
)
from .session_store import RedisSessionStore


class SetCacheFn(Protocol):
    def __call__(
        self,
        key: str,
        value: Mapping[str, object],
        timeout: int = 300,
    ) -> None: ...


settings = load_settings()

BASE_DIR = Path(__file__).resolve().parent.parent
FRONTEND_DIST_DIR = BASE_DIR.parent / "frontend" / "dist"
FRONTEND_STATIC_DIR = FRONTEND_DIST_DIR / "static"
PLANS_CACHE_DIR = BASE_DIR / "plans_cache"
AUTH_CODES_FILE = BASE_DIR / "auth_codes.json"

PLANS_CACHE_DIR.mkdir(parents=True, exist_ok=True)

SESSION_COOKIE_NAME = "session"
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"
SESSION_LIFETIME_SECONDS = int(timedelta(days=7).total_seconds())
SESSION_DAILY_REFRESH_SECONDS = 86400
SESSION_KEY_PREFIX = "3hk_user_"
SESSION_SECRET = settings.session_secret
COOKIE_SECURE = settings.cookie_secure
REDIS_URL = settings.redis_url
REDIS_SESSION_PREFIX = settings.redis_session_prefix
PROXIES = settings.proxies
TRUSTED_PROXY_IPS = settings.trusted_proxy_ips
METRICS_SECRET = settings.metrics_secret

BASE_HEADERS: dict[str, str] = {
    "Host": "www.three.com.hk",
    "Content-Type": "application/json",
    "Pragma": "no-cache",
    "Accept": "application/json, text/plain, */*",
    "Sec-Fetch-Site": "same-origin",
    "Accept-Language": "zh-TW,zh-Hant;q=0.9",
    "platformId": "GENERIC_ACCOUNT",
    "Sec-Fetch-Mode": "cors",
    "Accept-Encoding": "gzip, deflate, br",
    "Origin": "https://www.three.com.hk",
    "Referer": "https://www.three.com.hk/prepaid/account/tc/rnr-reg",
    "platformVersion": "0.55.0",
    "Connection": "keep-alive",
    "Sec-Fetch-Dest": "empty",
}

SUB_BRANDS = list(SUPPORTED_BRANDS)

retries = Retry(total=3, backoff_factor=0.5, status_forcelist=[500, 502, 503, 504])

CACHE_DEFAULT_TIMEOUT = 300
cache = MemoryCache(default_timeout=CACHE_DEFAULT_TIMEOUT)

plans_refresh_lock = threading.Lock()
plans_refreshing: set[str] = set()
redis_client = redis.Redis.from_url(
    REDIS_URL,
    decode_responses=True,
    socket_connect_timeout=3,
    socket_timeout=3,
    max_connections=16,
)
session_store = RedisSessionStore(
    redis_client=redis_client,
    key_prefix=REDIS_SESSION_PREFIX,
    lifetime_seconds=SESSION_LIFETIME_SECONDS,
    sid_prefix=SESSION_KEY_PREFIX,
)
password_cipher = create_password_cipher(settings.password_encryption_key)
auth_code_store = AuthCodeStore(
    redis_client=redis_client,
    seed_file=AUTH_CODES_FILE,
    key_mode=settings.auth_code_key_mode,
    hmac_key=settings.auth_code_hmac_key,
)
rate_limiter = RateLimiter(redis_client, settings.rate_limit)


def set_cache(key: str, value: Any, timeout: int = CACHE_DEFAULT_TIMEOUT) -> None:
    cache.set(key, value, timeout)


def get_cache(key: str) -> Any | None:
    return cache.get(key)


def delete_cache(key: str) -> None:
    cache.delete(key)


def encrypt_password(password: str | None) -> str | None:
    return encrypt_password_value(password_cipher, password)


def decrypt_password(encrypted_password: str | None) -> str | None:
    return decrypt_password_value(password_cipher, encrypted_password)


def verify_auth_code(auth_code: str | None, consume: bool = False) -> tuple[bool, str]:
    return auth_code_store.verify(auth_code, consume)


def get_isolated_session() -> requests.Session:
    s = requests.Session()
    # Closing a Session must not close another in-flight request's adapter.
    adapter = HTTPAdapter(pool_connections=4, pool_maxsize=4, max_retries=retries)
    s.mount("http://", adapter)
    s.mount("https://", adapter)
    return s
