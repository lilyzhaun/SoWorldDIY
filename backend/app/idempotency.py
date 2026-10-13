"""Durable, account-scoped deduplication for the three financial write routes."""

from __future__ import annotations

import hashlib
import hmac
import json
import logging
import re
from collections.abc import Awaitable, Callable
from functools import wraps
from typing import TYPE_CHECKING, cast

from fastapi import Request
from redis.exceptions import RedisError
from starlette.responses import JSONResponse, Response

from .blocking import run_blocking
from .public_errors import INVALID_REQUEST, SERVICE_UNAVAILABLE
from .responses import _public_error

if TYPE_CHECKING:
    from .routes.deps import RouteDeps

logger = logging.getLogger(__name__)
RETENTION_SECONDS = 86400
IDEMPOTENCY_OPENAPI = {
    "parameters": [
        {
            "name": "Idempotency-Key",
            "in": "header",
            "required": True,
            "description": "Random operation ID; reuse the same ID and body when retrying within 24 hours.",
            "schema": {
                "type": "string",
                "minLength": 32,
                "maxLength": 64,
                "pattern": "^[A-Za-z0-9_-]+$",
            },
        }
    ],
}
_REQUEST_ID = re.compile(r"[A-Za-z0-9_-]{32,64}\Z")
_CLAIM_SCRIPT = """
local previous = redis.call('GET', KEYS[1])
if previous then return previous end
redis.call('SETEX', KEYS[1], ARGV[2], ARGV[1])
return nil
"""
Handler = Callable[[Request], Awaitable[Response]]


class UpstreamWriteUncertain(RuntimeError):
    """The upstream may have completed a write; it must not be submitted again."""


def _unknown_result() -> JSONResponse:
    return JSONResponse(
        {
            "status": "error",
            "code": "upstream_result_unknown",
            "message": "操作结果待确认，请先核对交易记录或资源余额；不要重复提交或创建新订单",
        },
        status_code=409,
    )


def idempotent_write(deps: RouteDeps) -> Callable[[Handler], Handler]:
    def decorate(handler: Handler) -> Handler:
        @wraps(handler)
        async def wrapped(request: Request) -> Response:
            # Authenticate before looking up a cached result. The handler keeps
            # ownership/schema validation and its existing public error contract.
            ctx = deps._require_login(request)
            if ctx is None:
                return await handler(request)
            csrf_error = deps._validate_csrf(request, ctx)
            if csrf_error is not None:
                return csrf_error
            try:
                body = await request.json()
            except ValueError:
                return _public_error(INVALID_REQUEST, 400)
            if not isinstance(body, dict):
                return _public_error(INVALID_REQUEST, 400)
            account_id = body.get("account_id") or request.query_params.get(
                "account_id"
            )
            if not isinstance(account_id, str) or not deps.get_account_context(
                ctx, account_id
            ):
                return await handler(request)
            request_id = request.headers.get("idempotency-key", "")
            if not _REQUEST_ID.fullmatch(request_id):
                return _public_error(INVALID_REQUEST, 400)
            identity = json.dumps([account_id, request.url.path, request_id])
            digest = hmac.new(
                deps.SESSION_SECRET.encode(), identity.encode(), hashlib.sha256
            ).hexdigest()
            key = f"operation:{digest}"
            fingerprint = hashlib.sha256(
                json.dumps(body, sort_keys=True, separators=(",", ":")).encode()
            ).hexdigest()
            pending = {"fingerprint": fingerprint, "state": "pending"}
            try:
                previous = await run_blocking(
                    deps.redis_client.eval,
                    _CLAIM_SCRIPT,
                    1,
                    key,
                    json.dumps(pending),
                    str(RETENTION_SECONDS),
                )
            except RedisError:
                return _public_error(SERVICE_UNAVAILABLE, 503)
            if previous is not None:
                record = json.loads(cast(str, previous))
                if record["fingerprint"] != fingerprint:
                    return JSONResponse(
                        {
                            "status": "error",
                            "code": "idempotency_conflict",
                            "message": "同一订单标识不能用于不同请求",
                        },
                        status_code=409,
                    )
                if record["state"] != "done":
                    return _unknown_result()
                return Response(
                    record["body"],
                    status_code=record["status"],
                    media_type="application/json",
                )

            request.state.idempotent_write = True
            request.state.financial_write_started = False
            try:
                response = await handler(request)
            except UpstreamWriteUncertain:
                response = _unknown_result()
            # A handler's parse failure after POST is also an unknown outcome.
            if request.state.financial_write_started and response.status_code >= 500:
                response = _unknown_result()
            record = {
                "fingerprint": fingerprint,
                "state": "done",
                "status": response.status_code,
                "body": bytes(response.body).decode(),
            }
            try:
                await run_blocking(
                    deps.redis_client.set,
                    key,
                    json.dumps(record),
                    ex=RETENTION_SECONDS,
                    xx=True,
                )
            except RedisError:
                # Keep the known response; the existing pending record still
                # prevents a repeat if persistence fails after the upstream write.
                logger.error(
                    "Operation result persistence failed error_class=RedisError"
                )
            return response

        return wrapped

    return decorate
