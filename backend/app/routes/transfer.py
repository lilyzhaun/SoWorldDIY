from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from pydantic import ValidationError
from starlette.responses import Response

from ..schemas import TransferRequest
from ..services_transfer import (
    build_transfer_payload,
    select_dto_offer,
    select_transfer_product_id,
)
from ..upstream_urls import simworld_url
from .deps import RouteDeps

logger = logging.getLogger(__name__)


def register_transfer_routes(app: FastAPI, deps: RouteDeps) -> None:
    @app.post("/api/sim/transfer")
    async def transfer_resource(request: Request) -> Response:
        ctx = deps._require_login(request)
        if not ctx:
            return deps._redirect_to_login()
        csrf_error = deps._validate_csrf(request, ctx)
        if csrf_error:
            return csrf_error

        raw = await request.json()
        try:
            body = TransferRequest.model_validate(raw)
        except ValidationError as exc:
            return deps._json_error(str(exc), 400)

        req_ident = str(body.account_id)
        account_ctx = deps.get_account_context(ctx, req_ident)
        if not account_ctx:
            return deps._redirect_to_login()

        sid = body.subscriptionId
        target_brand = deps.get_brand_by_sub_id(ctx, str(sid), req_ident)
        try:
            tr = deps.make_3hk_request(
                request=request,
                ctx=ctx,
                method="GET",
                url=simworld_url(target_brand, "offer/getTransferOffers"),
                params={"subscriptionId": sid},
                account_id=req_ident,
                account_context=account_ctx,
            )
            if not tr:
                return deps._json_error("Request failed", 400)

            dto = select_dto_offer(tr.json().get("offers", []))
            if not dto:
                return deps._json_error("不支持转移", 400)

            target_product_id = select_transfer_product_id(dto, body.productFamily)
            payload = build_transfer_payload(
                dto_offer_id=dto["offerId"],
                target_product_id=target_product_id,
                source_msisdn=str(body.sourceMsisdn),
                subscription_id=sid,
                target_msisdn=str(body.targetMsisdn),
                user_offer_id=body.userOfferId,
                balance_resource_id=int(body.balanceResourceId),
                unit=body.unit,
                amount=float(body.amount),
            )

            r = deps.make_3hk_request(
                request=request,
                ctx=ctx,
                method="POST",
                url=simworld_url(target_brand, "sim/transferData"),
                json_data=payload,
                account_id=req_ident,
                account_context=account_ctx,
            )
            if r and r.status_code == 200:
                deps.delete_cache(f"profile_{req_ident}")
                return deps._json_success({"status": "success"})
            return deps._upstream_error(r, "资源转移请求失败，请稍后重试", 400)
        except Exception as exc:
            logger.exception(
                "transfer_resource failed brand=%s sid=%s account_id=%s",
                target_brand,
                sid,
                req_ident,
            )
            return deps._json_error(str(exc), 500)
