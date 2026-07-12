from __future__ import annotations

import logging
from typing import Any, TypedDict

from fastapi import FastAPI, Request
from fastapi.responses import RedirectResponse
from starlette.responses import Response

from .deps import RouteDeps

logger = logging.getLogger(__name__)

class DTOAgg(TypedDict):
    usages: list[dict[str, Any]]
    dates: list[str]
    is_vowifi: bool

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

        available_accounts: list[dict[str, Any]] = []
        for key, val in ctx.data.get("accounts", {}).items():
            available_accounts.append(
                {
                    "identifier": key,
                    "active": str(key) == str(req_ident),
                    "subBrand": val.get("sub_brand", "THREE"),
                }
            )

        agg: dict[str, dict[str, Any]] = {}
        user_email = ""

        def safe_date_str(val: Any) -> str:
            if val and isinstance(val, str) and "T" in val:
                return val.split("T")[0]
            return ""

        def fuzzy_time_key(val: Any) -> Any:
            if val and isinstance(val, str) and len(val) >= 16:
                return val[:16]
            return val

        for brand in deps.SUB_BRANDS:
            try:
                r = deps.make_3hk_request(
                    request=request,
                    ctx=ctx,
                    method="GET",
                    url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{brand}/user/getProfile",
                    account_id=req_ident,
                    account_context=account_ctx,
                )
                if r and r.status_code == 200:
                    data = r.json()
                    if not user_email and data.get("email"):
                        user_email = data.get("email", "")
                    subscriptions = data.get("subscriptions", [])
                    for sub in subscriptions:
                        mobile = sub.get("primaryMsisdn")
                        if not mobile or mobile in agg:
                            continue

                        raw_offers = sub.get("subscriptionOffers", [])
                        dto_sender_map: dict[Any, Any] = {}
                        for offer in raw_offers:
                            if offer.get("offerSubType") == "DTO":
                                sender = offer.get("transferFromMsisdn")
                                end_date = offer.get("endDate")
                                if sender and end_date:
                                    dto_sender_map[fuzzy_time_key(end_date)] = sender

                        active_offers: list[dict[str, Any]] = []
                        dto_voice_agg: DTOAgg = {
                            "usages": [],
                            "dates": [],
                            "is_vowifi": False,
                        }
                        dto_data_agg: DTOAgg = {
                            "usages": [],
                            "dates": [],
                            "is_vowifi": False,
                        }

                        for offer in raw_offers:
                            if offer.get("planStatus") not in ["ACTIVE", "PREACTIVE"]:
                                continue
                            offer_type = offer.get("offerType")
                            sub_type = offer.get("offerSubType")
                            is_dto = sub_type == "DTO"
                            is_vas = offer_type == "VAS"
                            if not (is_vas or is_dto):
                                continue

                            is_vowifi = False
                            raw_products = offer.get("subscriptionProducts", [])
                            for prod in raw_products:
                                if "VOWIFI" in str(
                                    prod.get("productName", "")
                                ).upper().replace(" ", ""):
                                    is_vowifi = True
                                    break

                            current_offer_id = offer.get("offerId")
                            offer_transfer = offer.get("transferAllowed", False)
                            usage_list: list[dict[str, Any]] = []

                            for prod in raw_products:
                                prod_transfer = prod.get("transferAllowed", False)
                                min_quota = prod.get("minTransferQuota", 0)
                                spec_type = str(prod.get("productSpecType", "")).upper()
                                if "VOICE" in spec_type:
                                    p_family = "VOICE"
                                elif "DATA" in spec_type:
                                    p_family = "DATA"
                                else:
                                    p_family = prod.get("productFamily", "DATA")

                                for bal in prod.get("matrixxBalanceInfos", []):
                                    if bal.get("unit") in ["Money", "HKD"]:
                                        continue
                                    total = float(bal.get("grantAmount", 0))
                                    remain = float(bal.get("amount", 0))
                                    if total > 0 or remain > 0:
                                        usage_list.append(
                                            {
                                                "name": prod.get("productName"),
                                                "unit": bal.get("unit"),
                                                "total": total,
                                                "remain": remain,
                                                "percent": (remain / total * 100)
                                                if total > 0
                                                else 0,
                                                "canTransfer": offer_transfer
                                                or prod_transfer,
                                                "minTransfer": min_quota,
                                                "balanceResourceId": bal.get(
                                                    "resourceId",
                                                    bal.get("balanceResourceId"),
                                                ),
                                                "productFamily": p_family,
                                                "userOfferId": current_offer_id,
                                            }
                                        )

                            if is_dto:
                                if usage_list:
                                    end_date_raw = offer.get("endDate", "")
                                    end_date_str = safe_date_str(end_date_raw)
                                    sender = offer.get(
                                        "transferFromMsisdn"
                                    ) or dto_sender_map.get(
                                        fuzzy_time_key(end_date_raw),
                                        "未知好友",
                                    )
                                    formatted_name = f"來自{sender} {end_date_str}結束"
                                    for usage in usage_list:
                                        usage["name"] = formatted_name
                                        target_agg = (
                                            dto_voice_agg
                                            if usage["productFamily"] == "VOICE"
                                            else dto_data_agg
                                        )
                                        target_agg["usages"].append(usage)
                                        if end_date_str:
                                            target_agg["dates"].append(end_date_str)
                                        if is_vowifi:
                                            target_agg["is_vowifi"] = True
                            else:
                                if usage_list or is_vas:
                                    active_offers.append(
                                        {
                                            "offerId": current_offer_id,
                                            "name": offer.get(
                                                "offerNameChi", offer.get("offerName")
                                            ),
                                            "desc": offer.get(
                                                "offerDescChi", offer.get("offerDesc")
                                            ),
                                            "price": offer.get("offerPrice", 0),
                                            "endDate": safe_date_str(
                                                offer.get("endDate")
                                            ),
                                            "isVoWifi": is_vowifi,
                                            "planStatus": offer.get("planStatus"),
                                            "usage": usage_list,
                                        }
                                    )

                        if dto_voice_agg["usages"]:
                            active_offers.append(
                                {
                                    "offerId": "DTO_VOICE_AGG",
                                    "name": "轉入的分鐘",
                                    "desc": "來自好友互傳的語音資源聚合",
                                    "price": 0,
                                    "endDate": max(dto_voice_agg["dates"])
                                    if dto_voice_agg["dates"]
                                    else "",
                                    "isVoWifi": dto_voice_agg["is_vowifi"],
                                    "planStatus": "ACTIVE",
                                    "usage": dto_voice_agg["usages"],
                                }
                            )
                        if dto_data_agg["usages"]:
                            active_offers.append(
                                {
                                    "offerId": "DTO_DATA_AGG",
                                    "name": "轉入的數據",
                                    "desc": "來自好友互傳的上網數據聚合",
                                    "price": 0,
                                    "endDate": max(dto_data_agg["dates"])
                                    if dto_data_agg["dates"]
                                    else "",
                                    "isVoWifi": dto_data_agg["is_vowifi"],
                                    "planStatus": "ACTIVE",
                                    "usage": dto_data_agg["usages"],
                                }
                            )

                        agg[mobile] = {
                            "mobile": mobile,
                            "activationDate": safe_date_str(sub.get("activationDate")),
                            "subsEndDate": safe_date_str(sub.get("subsEndDate")),
                            "subscriptionId": sub.get("subscriptionId"),
                            "brand": brand,
                            "iccid": sub.get("iccid", ""),
                            "status": sub.get("status", ""),
                            "activeOffers": active_offers,
                        }
            except Exception as exc:
                logger.error("Err parsing %s: %s", brand, exc)
                continue

        subscriptions_list = list(agg.values())
        result = {
            "status": "success",
            "data": {
                "email": user_email,
                "subscriptions": subscriptions_list,
                "current": subscriptions_list[0] if subscriptions_list else {},
                "available_accounts": available_accounts,
            },
        }
        if subscriptions_list:
            deps.set_cache(f"profile_{req_ident}", result)
        return deps._json_success(result)
