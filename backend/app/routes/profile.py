from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from ..services_profile import fetch_and_build_profile
from .deps import RouteDeps


def register_profile_routes(app: FastAPI, deps: RouteDeps) -> None:
    @app.get("/api/profile")
    async def get_profile_api(request: Request) -> Response:
        ctx = deps._require_login(request)
        if not ctx:
            return RedirectResponse(url="/", status_code=302)

        req_ident = request.query_params.get("account_id")
        if not req_ident:
            return deps._json_error("Missing account_id", 400)

        account_ctx = deps.get_account_context(ctx, req_ident)
        if not account_ctx:
            return deps._json_error("Invalid account", 401)

        if request.query_params.get("refresh") == "true":
            deps.delete_cache(f"profile_{req_ident}")

        cached = deps.get_cache(f"profile_{req_ident}")
        if cached:
            return deps._json_success(cached)

        result = fetch_and_build_profile(
            brands=deps.SUB_BRANDS,
            make_request=deps.make_3hk_request,
            request=request,
            ctx=ctx,
            req_ident=req_ident,
            account_ctx=account_ctx,
            accounts=ctx.data.get("accounts", {}),
        )
        subscriptions_list = result.get("data", {}).get("subscriptions", [])
        if subscriptions_list:
            deps.set_cache(f"profile_{req_ident}", result)
        return deps._json_success(result)
