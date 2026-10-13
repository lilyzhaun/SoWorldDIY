from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from starlette.responses import Response

from ..blocking import run_blocking
from ..public_errors import INTERNAL_ERROR
from ..responses import _public_error
from ..upstream_urls import simworld_url
from .deps import RouteDeps

logger = logging.getLogger(__name__)


def register_messages_routes(app: FastAPI, deps: RouteDeps) -> None:
    @app.get("/api/inbox")
    async def get_inbox(request: Request) -> Response:
        ctx = deps._require_login(request)
        if not ctx:
            return deps._redirect_to_login()

        req_ident = request.query_params.get("account_id")
        account_ctx = deps.get_account_context(ctx, req_ident)
        if not account_ctx:
            return deps._redirect_to_login()

        messages: list[dict[str, Any]] = []
        seen: set[Any] = set()
        brand = account_ctx.get("sub_brand", "THREE")
        try:
            r = await run_blocking(
                deps.make_3hk_request,
                request=request,
                ctx=ctx,
                method="GET",
                url=simworld_url(brand, "inbox/getMessages"),
                params={"lang": "tc"},
                account_id=req_ident,
                account_context=account_ctx,
            )
            if r and r.status_code == 200:
                for msg in r.json().get("inbox_msgs", []):
                    msg_id = msg.get("msg_id")
                    if msg_id not in seen:
                        messages.append(msg)
                        seen.add(msg_id)
        except Exception as exc:
            logger.error(
                "get_inbox failed error_class=%s brand=%s",
                type(exc).__name__,
                brand,
            )
        return deps._json_success(
            {
                "status": "success",
                "messages": sorted(
                    messages, key=lambda x: x.get("post_dt", ""), reverse=True
                ),
            }
        )

    @app.get("/api/history")
    async def get_transaction_history(request: Request) -> Response:
        ctx = deps._require_login(request)
        if not ctx:
            return deps._redirect_to_login()

        req_ident = request.query_params.get("account_id")
        account_ctx = deps.get_account_context(ctx, req_ident)
        if not account_ctx:
            return deps._redirect_to_login()

        sid = request.query_params.get("subscriptionId")
        target_brand = deps.get_brand_by_sub_id(ctx, sid, req_ident)
        params = {
            "type": "SUBSCRIPTION",
            "subscriptionId": sid,
            "startDate": request.query_params.get("startDate"),
            "endDate": request.query_params.get("endDate"),
        }
        try:
            r = await run_blocking(
                deps.make_3hk_request,
                request=request,
                ctx=ctx,
                method="GET",
                url=simworld_url(target_brand, "pmt/TransactionHistory"),
                params=params,
                account_id=req_ident,
                account_context=account_ctx,
            )
            if r and r.status_code == 200:
                return deps._json_success({"status": "success", "data": r.json()})
            return JSONResponse(status_code=400, content={"status": "error"})
        except Exception as exc:
            logger.error(
                "get_transaction_history failed error_class=%s brand=%s",
                type(exc).__name__,
                target_brand,
            )
            return _public_error(INTERNAL_ERROR, 500)
