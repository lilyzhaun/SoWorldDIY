from __future__ import annotations

import json
import logging
import threading
from typing import Any

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import Response

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
        target_brand = (
            brand_override
            if brand_override
            else deps.get_brand_by_sub_id(ctx, sub_id, req_ident)
        )

        cache_file = deps.PLANS_CACHE_DIR / f"plans_{target_brand}.json"
        curr_cookies = account_ctx.get("cookies", {})
        curr_ua = request.headers.get("User-Agent")

        if cache_file.exists():
            try:
                cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
                threading.Thread(
                    target=deps.fetch_and_save_plans_background,
                    args=(target_brand, curr_cookies, curr_ua),
                ).start()
                return deps._json_success(cached_data)
            except Exception:
                pass

        deps.fetch_and_save_plans_background(target_brand, curr_cookies, curr_ua)
        if cache_file.exists():
            return deps._json_success(json.loads(cache_file.read_text(encoding="utf-8")))
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
                url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{target_brand}/sim/{sid}/WalletBalances",
                account_id=req_ident,
                account_context=account_ctx,
            )
            data = r.json() if r and r.status_code == 200 else []
            balance = (
                max(float(item.get("amount", 0)) for item in data if "amount" in item)
                if isinstance(data, list) and data
                else 0
            )
            return deps._json_success({"status": "success", "balance": balance})
        except Exception:
            return deps._json_success({"status": "success", "balance": 0})

    @app.post("/api/purchase")
    async def purchase_plan(request: Request) -> Response:
        ctx = deps._require_login(request)
        if not ctx:
            return deps._redirect_to_login()
        csrf_error = deps._validate_csrf(request, ctx)
        if csrf_error:
            return csrf_error

        data = await request.json()
        req_ident = data.get("account_id") or request.query_params.get("account_id")
        account_ctx = deps.get_account_context(
            ctx, str(req_ident) if req_ident is not None else None
        )
        if not account_ctx:
            return deps._json_error("Auth failed", 401)

        sid = data.get("subscriptionId")
        new_line = bool(data.get("new_line", False))
        target_brand = deps.get_brand_by_sub_id(ctx, str(sid), str(req_ident))
        try:
            kr = deps.make_3hk_request(
                request=request,
                ctx=ctx,
                method="GET",
                url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{target_brand}/pmt/accessPurchaseKey",
                account_id=str(req_ident),
                account_context=account_ctx,
            )
            if not kr:
                return deps._json_error("Request failed", 400)
            access_key = kr.json().get("accessPurchaseKey")
            txn = float(data.get("txnAmount", 0))
            pmt: dict[str, Any] = {"amnt": max(0.0, float(data.get("price", 0)) - txn)}
            if pmt["amnt"] > 0:
                pmt.update({"lang": "tc", "type": data.get("paymentType", "ALCN")})

            if new_line:
                offers_payload = [
                    {
                        "offerId": "H3OF00000000001",
                        "quantity": 1,
                        "autoRenewFlag": False,
                    },
                ]
                for item in data.get("items", []):
                    if item.get("offerId") != "H3OF00000000001":
                        offers_payload.append(
                            {
                                "offerId": item["offerId"],
                                "quantity": int(item["quantity"]),
                                "autoRenewFlag": False,
                            }
                        )
                payload = {
                    "fUrl": "https://www.three.com.hk/prepaid/DIY/tc/checkout/payment/finished?actionflow=NEWSIM&purchaseid={purchaseid}",
                    "accessPurchaseKey": access_key,
                    "purchaseType": "PREPAID_DIY",
                    "order": {
                        "channel": "GLOBAL_ESIM",
                        "autoPayFlag": False,
                        "pmt": pmt,
                        "orderSubscription": {
                            "lang": "tc",
                            "offers": offers_payload,
                            "promoOptOuts": [],
                            "simType": "ESIM",
                        },
                    },
                }
            else:
                offers_payload = [
                    {
                        "offerId": item["offerId"],
                        "quantity": int(item["quantity"]),
                        "autoRenewFlag": False,
                    }
                    for item in data.get("items", [])
                ]
                sub_payload: dict[str, Any] = {
                    "lang": "tc",
                    "subscriptionId": sid,
                    "offers": offers_payload,
                }
                if txn > 0:
                    sub_payload["walletPayment"] = {"txnAmount": txn}
                payload = {
                    "fUrl": "https://simworld.net/SIMworld/main/tc",
                    "purchaseType": "SOSIM_VAS",
                    "accessPurchaseKey": access_key,
                    "order": {
                        "channel": "ONLINE",
                        "autoPayFlag": False,
                        "lang": "tc",
                        "pmt": pmt,
                        "orderSubscriptions": [sub_payload],
                    },
                }
            r = deps.make_3hk_request(
                request=request,
                ctx=ctx,
                method="POST",
                url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{target_brand}/pmt/purchase/createPurchase/",
                json_data=payload,
                account_id=str(req_ident),
                account_context=account_ctx,
            )
            if r and r.status_code == 200 and "paymentUrl" in r.json():
                deps.delete_cache(f"profile_{req_ident}")
                deps.handle_purchase_event(
                    r.json()["paymentUrl"], str(sid), pmt["amnt"], str(req_ident)
                )
                return deps._json_success(
                    {"status": "success", "paymentUrl": r.json()["paymentUrl"]}
                )
            return deps._upstream_error(r, "购买请求失败，请稍后重试", 400)
        except Exception as exc:
            return deps._json_error(str(exc), 500)
