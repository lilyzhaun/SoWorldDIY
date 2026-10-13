from __future__ import annotations

import logging
import secrets

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from redis.exceptions import RedisError
from starlette.responses import Response

from ..blocking import run_blocking
from ..cache_store import profile_cache_key
from ..public_errors import REDIS_UNAVAILABLE, SERVICE_UNAVAILABLE, UNAUTHORIZED
from ..responses import _public_error
from .deps import RouteDeps

logger = logging.getLogger(__name__)

_LOGOUT_OPENAPI = {
    "parameters": [
        {
            "name": "x-csrf-token",
            "in": "header",
            "required": False,
            "schema": {"type": "string"},
            "description": "CSRF token from csrf_token cookie; required when a session exists.",
        }
    ],
    "requestBody": {
        "required": False,
        "content": {
            "application/x-www-form-urlencoded": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "account_id": {
                            "type": "string",
                            "description": "Optional account to remove; omit to clear the whole session.",
                        }
                    },
                }
            }
        },
    },
}


def register_session_routes(app: FastAPI, deps: RouteDeps) -> None:
    @app.post("/logout", openapi_extra=_LOGOUT_OPENAPI)
    async def logout(request: Request) -> Response:
        ctx = getattr(request.state, "session_ctx", None)
        if ctx is None:
            deps._mark_session_cookie_for_deletion(request)
            return RedirectResponse(url="/", status_code=302)

        csrf_error = deps._validate_csrf(request, ctx)
        if csrf_error:
            return csrf_error

        form = await request.form()
        req_ident_raw = form.get("account_id")
        req_ident = str(req_ident_raw) if req_ident_raw else None

        if req_ident:
            try:
                has_left = await run_blocking(
                    deps.internal_logout_account, ctx, req_ident
                )
            except RuntimeError as exc:
                logger.error(
                    "logout failed operation=logout_account error_class=%s",
                    type(exc).__name__,
                )
                return _public_error(SERVICE_UNAVAILABLE, 503)
            if not has_left:
                deps._mark_session_cookie_for_deletion(request)
                return RedirectResponse(url="/", status_code=302)
            accounts = ctx.data.get("accounts", {})
            if accounts:
                first_id = list(accounts.keys())[0]
                return RedirectResponse(url=f"/main/{first_id}", status_code=302)

        account_ids = list(ctx.data.get("accounts", {}))
        try:
            await run_blocking(deps._clear_session, ctx)
        except RuntimeError as exc:
            logger.error(
                "logout failed operation=logout_clear error_class=%s",
                type(exc).__name__,
            )
            return _public_error(SERVICE_UNAVAILABLE, 503)
        for account_id in account_ids:
            deps.delete_cache(profile_cache_key(ctx.sid, account_id))
        deps._mark_session_cookie_for_deletion(request)
        return RedirectResponse(url="/", status_code=302)

    @app.post("/internal/session-cleanup")
    async def session_cleanup(request: Request) -> JSONResponse:
        provided_secret = request.headers.get("x-session-secret", "")
        expected = deps.SESSION_SECRET
        if not secrets.compare_digest(
            provided_secret.encode("utf-8"), expected.encode("utf-8")
        ):
            return _public_error(UNAUTHORIZED, 401)

        try:
            redis_ok = bool(await run_blocking(deps.redis_client.ping))
        except RedisError:
            logger.error(
                "session_cleanup failed operation=session_cleanup error_class=RedisError",
            )
            return _public_error(REDIS_UNAVAILABLE, 503)

        return deps._json_success({"redis_ok": redis_ok})
