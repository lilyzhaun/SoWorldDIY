from __future__ import annotations

import logging
from typing import Any

from fastapi import FastAPI, Request
from pydantic import ValidationError
from starlette.responses import Response

from ..schemas import CmnPurchaseRequest
from ..upstream_urls import SIMWORLD_PAYMENT_FINISHED, simworld_url
from .deps import RouteDeps

logger = logging.getLogger(__name__)


def register_cmn_routes(app: FastAPI, deps: RouteDeps) -> None:
    @app.get("/api/cmn/check")
    async def check_cmn(request: Request) -> Response:
        ctx = deps._require_login(request)
        if not ctx:
            return deps._redirect_to_login()

        req_ident = request.query_params.get("account_id")
        account_ctx = deps.get_account_context(ctx, req_ident)
        if not account_ctx:
            return deps._redirect_to_login()

        sid = request.query_params.get("subscriptionId")
        target_brand = deps.get_brand_by_sub_id(ctx, sid, req_ident)
        r = deps.make_3hk_request(
            request=request,
            ctx=ctx,
            method="GET",
            url=simworld_url(target_brand, "offer/getCmnOffer"),
            account_id=req_ident,
            account_context=account_ctx,
        )
        offers = r.json().get("offers", []) if r and r.status_code == 200 else []
        if not offers:
            return deps._json_error("无资格", 400)
        offer = offers[0]
        return deps._json_success(
            {
                "status": "success",
                "data": {
                    "offerId": offer["offerId"],
                    "offerSubType": offer["offerSubType"],
                    "price": offer["offerPrice"],
                    "name": offer["offerNameChi"],
                },
            }
        )

    @app.api_route("/api/cmn/numbers", methods=["GET", "POST"])
    async def get_cmn_numbers(request: Request) -> Response:
        ctx = deps._require_login(request)
        if not ctx:
            return deps._redirect_to_login()
        if request.method == "POST":
            csrf_error = deps._validate_csrf(request, ctx)
            if csrf_error:
                return csrf_error

        if request.method == "GET":
            req_ident = request.query_params.get("account_id")
            sid = request.query_params.get("subscriptionId")
        else:
            form = await request.form()
            req_ident = str(form.get("account_id")) if form.get("account_id") else None
            sid = (
                str(form.get("subscriptionId")) if form.get("subscriptionId") else None
            )

        account_ctx = deps.get_account_context(ctx, req_ident)
        if not account_ctx:
            return deps._redirect_to_login()

        target_brand = deps.get_brand_by_sub_id(ctx, sid, req_ident)
        r = deps.make_3hk_request(
            request=request,
            ctx=ctx,
            method="POST",
            url=simworld_url(target_brand, "mnms/holdAvailableNumbersFor15m/9/"),
            account_id=req_ident,
            account_context=account_ctx,
        )
        if not r or r.status_code != 200:
            return deps._json_error("Fetch failed", 400)
        numbers = sorted(set(r.json().get("lineList", [])))[:9]
        return deps._json_success({"status": "success", "numbers": numbers})

    @app.post("/api/cmn/purchase")
    async def purchase_cmn(request: Request) -> Response:
        ctx = deps._require_login(request)
        if not ctx:
            return deps._redirect_to_login()
        csrf_error = deps._validate_csrf(request, ctx)
        if csrf_error:
            return csrf_error

        raw = await request.json()
        try:
            body = CmnPurchaseRequest.model_validate(raw)
        except ValidationError as exc:
            return deps._json_error(str(exc), 400)

        req_ident = str(body.account_id)
        account_ctx = deps.get_account_context(ctx, req_ident)
        if not account_ctx:
            return deps._redirect_to_login()

        sid = body.subscriptionId
        target_brand = deps.get_brand_by_sub_id(ctx, str(sid), req_ident)
        try:
            kr = deps.make_3hk_request(
                request=request,
                ctx=ctx,
                method="GET",
                url=simworld_url(target_brand, "pmt/accessPurchaseKey"),
                account_id=req_ident,
                account_context=account_ctx,
            )
            if not kr:
                return deps._json_error("Request failed", 400)
            access_key = kr.json().get("accessPurchaseKey")
            txn = float(body.txnAmount)
            pmt_amt = max(0.0, float(body.price) - txn)
            pmt: dict[str, Any] = {"amnt": pmt_amt}
            order_sub: dict[str, Any] = {
                "msisdn": str(body.selectedNumber),
                "lang": "tc",
                "subscriptionId": sid,
                "offers": [{"offerId": body.offerId, "quantity": 1}],
            }
            if pmt_amt > 0:
                pmt.update({"lang": "tc", "type": body.paymentType})
            if txn > 0:
                order_sub["walletPayment"] = {"txnAmount": txn}

            payload = {
                "fUrl": SIMWORLD_PAYMENT_FINISHED,
                "purchaseType": "CMN_ONLY",
                "accessPurchaseKey": access_key,
                "order": {
                    "channel": "ONLINE",
                    "autoPayFlag": False,
                    "pmt": pmt,
                    "orderSubscription": order_sub,
                },
            }

            r = deps.make_3hk_request(
                request=request,
                ctx=ctx,
                method="POST",
                url=simworld_url(target_brand, "pmt/purchase/createPurchase/"),
                json_data=payload,
                account_id=req_ident,
                account_context=account_ctx,
            )
            if r and r.status_code == 200 and "paymentUrl" in r.json():
                deps.delete_cache(f"profile_{req_ident}")
                deps.handle_purchase_event(
                    r.json()["paymentUrl"], str(sid), pmt_amt, req_ident
                )
                return deps._json_success(
                    {"status": "success", "paymentUrl": r.json()["paymentUrl"]}
                )
            return deps._upstream_error(r, "换号购买请求失败，请稍后重试", 400)
        except Exception as exc:
            logger.exception(
                "purchase_cmn failed brand=%s sid=%s account_id=%s",
                target_brand,
                sid,
                req_ident,
            )
            return deps._json_error(str(exc), 500)
