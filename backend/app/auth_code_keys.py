"""Typed auth-code Redis key modes and versioned HMAC key derivation.

Modes are migration-staged: ``legacy`` (default) preserves plaintext keys;
``dual`` reads legacy or v2 and writes only v2; ``hmac`` is v2-only.
"""

from __future__ import annotations

import hashlib
import hmac
from enum import StrEnum
from typing import Final

LEGACY_KEY_PREFIX: Final[str] = "auth_code:"
V2_KEY_PREFIX: Final[str] = "auth_code:v2:"
V2_CODE_SHAPE_PREFIX: Final[str] = "v2:"
V2_DIGEST_HEX_LEN: Final[int] = 64
FINGERPRINT_HEX_LEN: Final[int] = 12
MIN_HMAC_KEY_BYTES: Final[int] = 32
_HEX_LOWER: Final[str] = "0123456789abcdef"


class AuthCodeKeyMode(StrEnum):
    """Staged Redis key modes for auth codes (migration window only for legacy/dual)."""

    LEGACY = "legacy"
    DUAL = "dual"
    HMAC = "hmac"


def parse_auth_code_key_mode(raw: str | None) -> AuthCodeKeyMode:
    """Parse ``AUTH_CODE_KEY_MODE``; empty/None defaults to ``legacy``."""
    if raw is None or not str(raw).strip():
        return AuthCodeKeyMode.LEGACY
    value = str(raw).strip().lower()
    try:
        return AuthCodeKeyMode(value)
    except ValueError as exc:
        raise ValueError(
            "AUTH_CODE_KEY_MODE must be one of: legacy, dual, hmac"
        ) from exc


def parse_auth_code_hmac_key(raw: str | None) -> bytes:
    """Require a dedicated secret of at least ``MIN_HMAC_KEY_BYTES`` UTF-8 bytes.

    Never embed the secret value in the error message.
    """
    if raw is None or not str(raw):
        raise ValueError(
            f"AUTH_CODE_HMAC_KEY is required and must be at least "
            f"{MIN_HMAC_KEY_BYTES} bytes"
        )
    key_bytes = str(raw).encode("utf-8")
    if len(key_bytes) < MIN_HMAC_KEY_BYTES:
        raise ValueError(
            f"AUTH_CODE_HMAC_KEY is required and must be at least "
            f"{MIN_HMAC_KEY_BYTES} bytes"
        )
    return key_bytes


def require_hmac_key_for_mode(mode: AuthCodeKeyMode, raw: str | None) -> bytes | None:
    """Return HMAC key bytes for dual/hmac; ``None`` only in legacy mode."""
    if mode is AuthCodeKeyMode.LEGACY:
        return None
    return parse_auth_code_hmac_key(raw)


def legacy_redis_key(auth_code: str, prefix: str = LEGACY_KEY_PREFIX) -> str:
    return f"{prefix}{auth_code}"


def v2_digest(hmac_key: bytes, auth_code: str) -> str:
    return hmac.new(hmac_key, auth_code.encode("utf-8"), hashlib.sha256).hexdigest()


def v2_redis_key(hmac_key: bytes, auth_code: str) -> str:
    return f"{V2_KEY_PREFIX}{v2_digest(hmac_key, auth_code)}"


def fingerprint_from_digest(digest_hex: str) -> str:
    return digest_hex[:FINGERPRINT_HEX_LEN]


def fingerprint_for_code(hmac_key: bytes, auth_code: str) -> str:
    return fingerprint_from_digest(v2_digest(hmac_key, auth_code))


def is_lowercase_hex(value: str, *, length: int) -> bool:
    return len(value) == length and all(ch in _HEX_LOWER for ch in value)


def is_v2_redis_key(key: str) -> bool:
    """True only for canonical v2 keys: prefix + exactly 64 lowercase hex chars."""
    if not key.startswith(V2_KEY_PREFIX):
        return False
    digest = key.removeprefix(V2_KEY_PREFIX)
    return is_lowercase_hex(digest, length=V2_DIGEST_HEX_LEN)


def is_legacy_redis_key(key: str, prefix: str = LEGACY_KEY_PREFIX) -> bool:
    return key.startswith(prefix) and not is_v2_redis_key(key)


def legacy_code_from_key(key: str, prefix: str = LEGACY_KEY_PREFIX) -> str:
    return key.removeprefix(prefix)


def v2_digest_from_key(key: str) -> str:
    if not is_v2_redis_key(key):
        raise ValueError("not a canonical v2 auth code redis key")
    return key.removeprefix(V2_KEY_PREFIX)


def is_reserved_v2_shaped_code(auth_code: str) -> bool:
    """Reject codes that collide with the canonical v2 redis key suffix shape.

    A legacy key is ``auth_code:{code}``. If ``code`` is exactly ``v2:`` plus
    64 lowercase hex digits, the resulting redis key is indistinguishable from a
    real v2 key and must not be created as a plaintext code.
    """
    if not auth_code.startswith(V2_CODE_SHAPE_PREFIX):
        return False
    digest = auth_code.removeprefix(V2_CODE_SHAPE_PREFIX)
    return is_lowercase_hex(digest, length=V2_DIGEST_HEX_LEN)
