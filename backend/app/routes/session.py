from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from redis.exceptions import RedisError

from .deps import RouteDeps

logger = logging.getLogger(__name__)

def register_session_routes(app: FastAPI, deps: RouteDeps) -> None:
    @app.get("/logout")
    async def logout(request: Request) -> RedirectResponse:
        ctx = getattr(request.state, "session_ctx", None)
        if ctx is None:
            deps._mark_session_cookie_for_deletion(request)
            return RedirectResponse(url="/", status_code=302)
        req_ident = request.query_params.get("account_id")
        if req_ident:
            try:
                has_left = deps.internal_logout_account(ctx, req_ident)
            except RuntimeError:
                deps._mark_session_cookie_for_deletion(request)
                return RedirectResponse(url="/", status_code=302)
            if not has_left:
                deps._mark_session_cookie_for_deletion(request)
                return RedirectResponse(url="/", status_code=302)
            accounts = ctx.data.get("accounts", {})
            if accounts:
                first_id = list(accounts.keys())[0]
                return RedirectResponse(url=f"/main/{first_id}", status_code=302)

        try:
            deps._clear_session(ctx)
        except RuntimeError:
            pass
        deps._mark_session_cookie_for_deletion(request)
        return RedirectResponse(url="/", status_code=302)

    @app.post("/internal/session-cleanup")
    async def session_cleanup(request: Request) -> JSONResponse:
        provided_secret = request.headers.get("x-session-secret", "")
        if provided_secret != deps.SESSION_SECRET:
            return deps._json_error("Unauthorized", 401)

        try:
            redis_ok = bool(deps.redis_client.ping())
        except RedisError as exc:
            return deps._json_error(f"Redis unavailable: {exc}", 503)

        return deps._json_success({"redis_ok": redis_ok})
