from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from starlette.responses import Response

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

        data = await request.json()
        req_ident = str(data.get("account_id", ""))
        account_ctx = deps.get_account_context(ctx, req_ident)
        if not account_ctx:
            return deps._redirect_to_login()

        sid = data.get("subscriptionId")
        target_brand = deps.get_brand_by_sub_id(ctx, str(sid), req_ident)
        try:
            tr = deps.make_3hk_request(
                request=request,
                ctx=ctx,
                method="GET",
                url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{target_brand}/offer/getTransferOffers",
                params={"subscriptionId": sid},
                account_id=req_ident,
                account_context=account_ctx,
            )
            if not tr:
                return deps._json_error("Request failed", 400)
            dto = next(
                (
                    o
                    for o in tr.json().get("offers", [])
                    if o.get("offerSubType") == "DTO"
                ),
                None,
            )
            if not dto:
                return deps._json_error("不支持转移", 400)

            target_product_id = next(
                (
                    p["productId"]
                    for p in dto.get("products", [])
                    if p.get("productFamily") == data.get("productFamily")
                ),
                dto["products"][0]["productId"],
            )
            payload = {
                "tranferOrder": {
                    "channel": "WEB",
                    "orderSubscription": {
                        "msisdn": str(data.get("sourceMsisdn")),
                        "subscriptionId": sid,
                        "volumeUpMsisdn": str(data.get("targetMsisdn")),
                        "lang": "tc",
                        "offers": [
                            {
                                "offerId": dto["offerId"],
                                "transferOfferId": data.get("userOfferId"),
                                "offerProduct": {
                                    "balanceResourceId": int(
                                        data.get("balanceResourceId")
                                    ),
                                    "productId": target_product_id,
                                    "productData": {
                                        "unit": data.get("unit"),
                                        "volume": float(data.get("amount")),
                                    },
                                },
                            }
                        ],
                    },
                }
            }

            r = deps.make_3hk_request(
                request=request,
                ctx=ctx,
                method="POST",
                url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{target_brand}/sim/transferData",
                json_data=payload,
                account_id=req_ident,
                account_context=account_ctx,
            )
            if r and r.status_code == 200:
                deps.delete_cache(f"profile_{req_ident}")
                return deps._json_success({"status": "success"})
            return deps._upstream_error(r, "资源转移请求失败，请稍后重试", 400)
        except Exception as exc:
            return deps._json_error(str(exc), 500)
