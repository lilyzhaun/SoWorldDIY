"""HTTP helpers for rate-limit decisions (auth routes)."""

from __future__ import annotations

from fastapi import Request
from fastapi.responses import JSONResponse

from .client_ip import resolve_client_ip
from .public_errors import RATE_LIMITED, SERVICE_UNAVAILABLE
from .rate_limit import RateLimitDecision
from .responses import _public_error


def client_ip(request: Request, trusted: frozenset[str]) -> str:
    peer = request.client.host if request.client else None
    return resolve_client_ip(
        peer=peer,
        x_forwarded_for=request.headers.get("x-forwarded-for"),
        trusted_proxies=trusted,
    )


def rate_limited_response(decision: RateLimitDecision) -> JSONResponse:
    return _public_error(
        RATE_LIMITED,
        429,
        headers={"Retry-After": str(max(1, int(decision.retry_after)))},
    )


def redis_unavailable_response() -> JSONResponse:
    return _public_error(SERVICE_UNAVAILABLE, 503)


def guard(decision: RateLimitDecision) -> JSONResponse | None:
    """Map a rate-limit decision to an HTTP response, or None if allowed."""
    if decision.redis_error:
        return redis_unavailable_response()
    if not decision.allowed:
        return rate_limited_response(decision)
    return None
