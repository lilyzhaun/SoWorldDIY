from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from pydantic import ValidationError
from starlette.responses import Response

from ..blocking import run_blocking
from ..cache_store import profile_cache_key
from ..idempotency import IDEMPOTENCY_OPENAPI, UpstreamWriteUncertain, idempotent_write
from ..public_errors import INTERNAL_ERROR, INVALID_REQUEST
from ..responses import _public_error
from ..schemas import CmnPurchaseRequest
from ..services_commerce import build_cmn_purchase_payload, parse_purchase_result
from ..services_validation import WriteValidationError, validate_cmn
from ..upstream_urls import simworld_url
from .deps import RouteDeps

logger = logging.getLogger(__name__)

_CMN_NUMBERS_OPENAPI = {
    "parameters": [
        {
            "name": "x-csrf-token",
            "in": "header",
            "required": True,
            "schema": {"type": "string"},
        }
    ],
    "requestBody": {
        "required": True,
        "content": {
            "application/x-www-form-urlencoded": {
                "schema": {
                    "type": "object",
                    "properties": {
                        "account_id": {"type": "string"},
                        "subscriptionId": {"type": "string"},
                    },
                }
            }
        },
    },
}


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
        r = await run_blocking(
            deps.make_3hk_request,
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

    async def _build_cmn_numbers(
        request: Request,
        ctx,
        req_ident: str | None,
        sid: str | None,
    ) -> Response:
        account_ctx = deps.get_account_context(ctx, req_ident)
        if not account_ctx:
            return deps._redirect_to_login()

        target_brand = deps.get_brand_by_sub_id(ctx, sid, req_ident)
        r = await run_blocking(
            deps.make_3hk_request,
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

    @app.post(
        "/api/cmn/numbers",
        name="post_cmn_numbers",
        operation_id="post_cmn_numbers",
        openapi_extra=_CMN_NUMBERS_OPENAPI,
    )
    async def post_cmn_numbers(request: Request) -> Response:
        ctx = deps._require_login(request)
        if not ctx:
            return deps._redirect_to_login()
        csrf_error = deps._validate_csrf(request, ctx)
        if csrf_error:
            return csrf_error
        form = await request.form()
        req_ident = str(form.get("account_id")) if form.get("account_id") else None
        sid = str(form.get("subscriptionId")) if form.get("subscriptionId") else None
        return await _build_cmn_numbers(
            request=request,
            ctx=ctx,
            req_ident=req_ident,
            sid=sid,
        )

    @app.post("/api/cmn/purchase", openapi_extra=IDEMPOTENCY_OPENAPI)
    @idempotent_write(deps)
    async def purchase_cmn(request: Request) -> Response:
        ctx = deps._require_login(request)
        if not ctx:
            return deps._redirect_to_login()
        csrf_error = deps._validate_csrf(request, ctx)
        if csrf_error:
            return csrf_error

        try:
            raw = await request.json()
        except ValueError:
            return _public_error(INVALID_REQUEST, 400)
        try:
            body = CmnPurchaseRequest.model_validate(raw)
        except ValidationError:
            return _public_error(INVALID_REQUEST, 400)

        req_ident = str(body.account_id)
        account_ctx = deps.get_account_context(ctx, req_ident)
        if not account_ctx:
            return deps._redirect_to_login()

        sid = body.subscriptionId
        target_brand = deps.get_brand_by_sub_id(ctx, str(sid), req_ident)
        try:
            target_brand = await run_blocking(
                validate_cmn, deps, request, ctx, req_ident, body
            )
            kr = await run_blocking(
                deps.make_3hk_request,
                request=request,
                ctx=ctx,
                method="GET",
                url=simworld_url(target_brand, "pmt/accessPurchaseKey"),
                account_id=req_ident,
                account_context=account_ctx,
            )
            if not kr:
                return deps._json_error("Request failed", 400)
            purchase = build_cmn_purchase_payload(
                body,
                kr.json().get("accessPurchaseKey"),
            )

            r = await run_blocking(
                deps.make_3hk_request,
                request=request,
                ctx=ctx,
                method="POST",
                url=simworld_url(target_brand, "pmt/purchase/createPurchase/"),
                json_data=purchase.payload,
                account_id=req_ident,
                account_context=account_ctx,
            )
            if r is not None and r.status_code == 200:
                result = parse_purchase_result(r.json())
                if result["status"] == "success":
                    deps.delete_cache(profile_cache_key(ctx.sid, req_ident))
                    return deps._json_success(result)
            elif r is not None and 200 <= r.status_code < 300:
                raise UpstreamWriteUncertain("Pending payment result")
            return deps._upstream_error(
                r,
                "换号购买请求失败，请稍后重试",
                400,
                operation="purchase_cmn",
            )
        except UpstreamWriteUncertain:
            raise
        except WriteValidationError as exc:
            return deps._json_error(str(exc), 400)
        except Exception as exc:
            logger.error(
                "purchase_cmn failed error_class=%s brand=%s",
                type(exc).__name__,
                target_brand,
            )
            return _public_error(INTERNAL_ERROR, 500)
