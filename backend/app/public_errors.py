"""Stable public error catalog for HTTP responses.

Internal exception details never cross the response boundary.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Final


class PublicErrorCode(StrEnum):
    """Machine-stable public error codes (no secrets)."""

    INVALID_REQUEST = "invalid_request"
    UNAUTHORIZED = "unauthorized"
    CSRF_INVALID = "csrf_invalid"
    AUTH_FAILED = "auth_failed"
    SERVICE_UNAVAILABLE = "service_unavailable"
    INTERNAL_ERROR = "internal_error"
    UPSTREAM_ERROR = "upstream_error"
    RATE_LIMITED = "rate_limited"


@dataclass(frozen=True, slots=True)
class PublicError:
    """Public-facing error payload fragments."""

    code: PublicErrorCode
    message: str


INVALID_REQUEST: Final = PublicError(
    PublicErrorCode.INVALID_REQUEST,
    "请求参数无效",
)
UNAUTHORIZED: Final = PublicError(
    PublicErrorCode.UNAUTHORIZED,
    "Unauthorized",
)
CSRF_INVALID: Final = PublicError(
    PublicErrorCode.CSRF_INVALID,
    "CSRF token invalid",
)
AUTH_FAILED: Final = PublicError(
    PublicErrorCode.AUTH_FAILED,
    "Auth failed",
)
SERVICE_UNAVAILABLE: Final = PublicError(
    PublicErrorCode.SERVICE_UNAVAILABLE,
    "服务暂时不可用",
)
INTERNAL_ERROR: Final = PublicError(
    PublicErrorCode.INTERNAL_ERROR,
    "服务暂时不可用，请稍后重试",
)
ACCOUNT_CHECK_FAILED: Final = PublicError(
    PublicErrorCode.INTERNAL_ERROR,
    "账号检查失败",
)
REDIS_UNAVAILABLE: Final = PublicError(
    PublicErrorCode.SERVICE_UNAVAILABLE,
    "Redis unavailable",
)
RATE_LIMITED: Final = PublicError(
    PublicErrorCode.RATE_LIMITED,
    "请求过于频繁，请稍后再试",
)
