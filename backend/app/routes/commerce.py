from __future__ import annotations

import logging
import threading

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from pydantic import ValidationError
from starlette.responses import Response

from ..brand import INVALID_BRAND_CODE, InvalidBrandError, parse_brand, plans_cache_path
from ..schemas import PurchaseRequest
from ..services_commerce import (
    build_plan_purchase_payload,
    load_plans_from_cache,
    parse_wallet_balance,
)
from ..upstream_urls import simworld_url
from .deps import RouteDeps

logger = logging.getLogger(__name__)


def register_commerce_routes(app: FastAPI, deps: RouteDeps) -> None:
    @app.get("/api/plans")
    async def get_plans_api(request: Request) -> Response:
        ctx = deps._require_login(request)
        if not ctx:
            return RedirectResponse(url="/", status_code=302)

        req_ident = request.query_params.get("account_id")
        account_ctx = deps.get_account_context(ctx, req_ident)
        if not account_ctx:
            return JSONResponse(status_code=401, content={"status": "error"})

        sub_id = request.query_params.get("subscriptionId")
        brand_override = request.query_params.get("brand")
        raw_brand = (
            brand_override
            if brand_override is not None
            else deps.get_brand_by_sub_id(ctx, sub_id, req_ident)
        )
        try:
            target_brand = parse_brand(raw_brand)
            cache_file = plans_cache_path(deps.PLANS_CACHE_DIR, target_brand)
        except InvalidBrandError:
            return deps._json_error(INVALID_BRAND_CODE, 400)

        curr_cookies = account_ctx.get("cookies", {})
        curr_ua = request.headers.get("User-Agent")

        cached_data = load_plans_from_cache(
            cache_file,
            cache_root=deps.PLANS_CACHE_DIR,
            brand=target_brand,
        )
        if cached_data is not None:
            threading.Thread(
                target=deps.fetch_and_save_plans_background,
                args=(target_brand, curr_cookies, curr_ua),
            ).start()
            return deps._json_success(cached_data)

        deps.fetch_and_save_plans_background(target_brand, curr_cookies, curr_ua)
        refreshed = load_plans_from_cache(
            cache_file,
            cache_root=deps.PLANS_CACHE_DIR,
            brand=target_brand,
        )
        if refreshed is not None:
            return deps._json_success(refreshed)
        return deps._json_error("Fetch plans failed", 400)

    @app.get("/api/balance")
    async def get_balance(request: Request) -> Response:
        ctx = deps._require_login(request)
        if not ctx:
            return deps._redirect_to_login()

        req_ident = request.query_params.get("account_id")
        account_ctx = deps.get_account_context(ctx, req_ident)
        if not account_ctx:
            return deps._json_success({"status": "success", "balance": 0})

        sid = request.query_params.get("subscriptionId")
        target_brand = deps.get_brand_by_sub_id(ctx, sid, req_ident)
        try:
            r = deps.make_3hk_request(
                request=request,
                ctx=ctx,
                method="GET",
                url=simworld_url(target_brand, "sim", str(sid), "WalletBalances"),
                account_id=req_ident,
                account_context=account_ctx,
            )
            data = r.json() if r and r.status_code == 200 else []
            balance = parse_wallet_balance(data)
            return deps._json_success({"status": "success", "balance": balance})
        except Exception:
            logger.exception(
                "get_balance failed brand=%s sid=%s account_id=%s",
                target_brand,
                sid,
                req_ident,
            )
            return deps._json_success({"status": "success", "balance": 0})

    @app.post("/api/purchase")
    async def purchase_plan(request: Request) -> Response:
        ctx = deps._require_login(request)
        if not ctx:
            return deps._redirect_to_login()
        csrf_error = deps._validate_csrf(request, ctx)
        if csrf_error:
            return csrf_error

        raw = await request.json()
        try:
            body = PurchaseRequest.model_validate(raw)
        except ValidationError as exc:
            return deps._json_error(str(exc), 400)

        req_ident = body.account_id or request.query_params.get("account_id")
        account_ctx = deps.get_account_context(
            ctx, str(req_ident) if req_ident is not None else None
        )
        if not account_ctx:
            return deps._json_error("Auth failed", 401)

        sid = body.subscriptionId
        target_brand = deps.get_brand_by_sub_id(ctx, str(sid), str(req_ident))
        try:
            kr = deps.make_3hk_request(
                request=request,
                ctx=ctx,
                method="GET",
                url=simworld_url(target_brand, "pmt/accessPurchaseKey"),
                account_id=str(req_ident),
                account_context=account_ctx,
            )
            if not kr:
                return deps._json_error("Request failed", 400)
            purchase = build_plan_purchase_payload(
                body,
                kr.json().get("accessPurchaseKey"),
            )
            r = deps.make_3hk_request(
                request=request,
                ctx=ctx,
                method="POST",
                url=simworld_url(target_brand, "pmt/purchase/createPurchase/"),
                json_data=purchase.payload,
                account_id=str(req_ident),
                account_context=account_ctx,
            )
            if r and r.status_code == 200 and "paymentUrl" in r.json():
                deps.delete_cache(f"profile_{req_ident}")
                deps.handle_purchase_event(
                    r.json()["paymentUrl"],
                    str(sid),
                    purchase.payable_amount,
                    str(req_ident),
                )
                return deps._json_success(
                    {"status": "success", "paymentUrl": r.json()["paymentUrl"]}
                )
            return deps._upstream_error(r, "购买请求失败，请稍后重试", 400)
        except Exception as exc:
            logger.exception(
                "purchase_plan failed brand=%s sid=%s account_id=%s",
                target_brand,
                sid,
                req_ident,
            )
            return deps._json_error(str(exc), 500)
