"""Profile aggregation: pure helpers + brand fetch/build for /api/profile."""

from __future__ import annotations

import logging
from collections.abc import Callable, Mapping, Sequence
from typing import Any, TypedDict

from fastapi import Request

from .session_store import SessionContext
from .upstream_urls import simworld_url

logger = logging.getLogger(__name__)


class DTOAgg(TypedDict):
    usages: list[dict[str, Any]]
    dates: list[str]
    is_vowifi: bool


def safe_date_str(val: Any) -> str:
    if val and isinstance(val, str) and "T" in val:
        return val.split("T")[0]
    return ""


def fuzzy_time_key(val: Any) -> Any:
    if val and isinstance(val, str) and len(val) >= 16:
        return val[:16]
    return val


def build_available_accounts(
    accounts: Mapping[str, Any],
    req_ident: str,
) -> list[dict[str, Any]]:
    available: list[dict[str, Any]] = []
    for key, val in accounts.items():
        available.append(
            {
                "identifier": key,
                "active": str(key) == str(req_ident),
                "subBrand": val.get("sub_brand", "THREE"),
            }
        )
    return available


def _product_family(prod: Mapping[str, Any]) -> str:
    spec_type = str(prod.get("productSpecType", "")).upper()
    if "VOICE" in spec_type:
        return "VOICE"
    if "DATA" in spec_type:
        return "DATA"
    return str(prod.get("productFamily", "DATA"))


def _is_vowifi_product(prod: Mapping[str, Any]) -> bool:
    name = str(prod.get("productName", "")).upper().replace(" ", "")
    return "VOWIFI" in name


def _build_usage_list(
    raw_products: Sequence[Mapping[str, Any]],
    *,
    offer_transfer: bool,
    current_offer_id: Any,
) -> list[dict[str, Any]]:
    usage_list: list[dict[str, Any]] = []
    for prod in raw_products:
        prod_transfer = prod.get("transferAllowed", False)
        min_quota = prod.get("minTransferQuota", 0)
        p_family = _product_family(prod)
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
                        "percent": (remain / total * 100) if total > 0 else 0,
                        "canTransfer": offer_transfer or prod_transfer,
                        "minTransfer": min_quota,
                        "balanceResourceId": bal.get(
                            "resourceId",
                            bal.get("balanceResourceId"),
                        ),
                        "productFamily": p_family,
                        "userOfferId": current_offer_id,
                    }
                )
    return usage_list


def build_active_offers(raw_offers: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Aggregate subscriptionOffers into the activeOffers list for one SIM."""
    dto_sender_map: dict[Any, Any] = {}
    for offer in raw_offers:
        if offer.get("offerSubType") == "DTO":
            sender = offer.get("transferFromMsisdn")
            end_date = offer.get("endDate")
            if sender and end_date:
                dto_sender_map[fuzzy_time_key(end_date)] = sender

    active_offers: list[dict[str, Any]] = []
    dto_voice_agg: DTOAgg = {"usages": [], "dates": [], "is_vowifi": False}
    dto_data_agg: DTOAgg = {"usages": [], "dates": [], "is_vowifi": False}

    for offer in raw_offers:
        if offer.get("planStatus") not in ["ACTIVE", "PREACTIVE"]:
            continue
        offer_type = offer.get("offerType")
        sub_type = offer.get("offerSubType")
        is_dto = sub_type == "DTO"
        is_vas = offer_type == "VAS"
        if not (is_vas or is_dto):
            continue

        raw_products = offer.get("subscriptionProducts", [])
        is_vowifi = any(_is_vowifi_product(prod) for prod in raw_products)
        current_offer_id = offer.get("offerId")
        offer_transfer = offer.get("transferAllowed", False)
        usage_list = _build_usage_list(
            raw_products,
            offer_transfer=bool(offer_transfer),
            current_offer_id=current_offer_id,
        )

        if is_dto:
            if usage_list:
                end_date_raw = offer.get("endDate", "")
                end_date_str = safe_date_str(end_date_raw)
                sender = offer.get("transferFromMsisdn") or dto_sender_map.get(
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
        elif usage_list or is_vas:
            active_offers.append(
                {
                    "offerId": current_offer_id,
                    "name": offer.get("offerNameChi", offer.get("offerName")),
                    "desc": offer.get("offerDescChi", offer.get("offerDesc")),
                    "price": offer.get("offerPrice", 0),
                    "endDate": safe_date_str(offer.get("endDate")),
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
                "endDate": max(dto_voice_agg["dates"]) if dto_voice_agg["dates"] else "",
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
                "endDate": max(dto_data_agg["dates"]) if dto_data_agg["dates"] else "",
                "isVoWifi": dto_data_agg["is_vowifi"],
                "planStatus": "ACTIVE",
                "usage": dto_data_agg["usages"],
            }
        )
    return active_offers


def build_subscription_entry(
    sub: Mapping[str, Any],
    brand: str,
) -> dict[str, Any] | None:
    """Turn one upstream subscription into the profile subscription dict."""
    mobile = sub.get("primaryMsisdn")
    if not mobile:
        return None
    raw_offers = sub.get("subscriptionOffers", [])
    return {
        "mobile": mobile,
        "activationDate": safe_date_str(sub.get("activationDate")),
        "subsEndDate": safe_date_str(sub.get("subsEndDate")),
        "subscriptionId": sub.get("subscriptionId"),
        "brand": brand,
        "iccid": sub.get("iccid", ""),
        "status": sub.get("status", ""),
        "activeOffers": build_active_offers(raw_offers),
    }


def merge_brand_profile_data(
    brand: str,
    data: Mapping[str, Any],
    agg: dict[str, dict[str, Any]],
    user_email: str,
) -> str:
    """Merge one brand getProfile JSON into agg; return updated user_email."""
    email = user_email
    if not email and data.get("email"):
        email = str(data.get("email", ""))
    for sub in data.get("subscriptions", []):
        mobile = sub.get("primaryMsisdn")
        if not mobile or mobile in agg:
            continue
        entry = build_subscription_entry(sub, brand)
        if entry is not None:
            agg[str(mobile)] = entry
    return email


def build_profile_result(
    *,
    user_email: str,
    subscriptions: list[dict[str, Any]],
    available_accounts: list[dict[str, Any]],
) -> dict[str, Any]:
    return {
        "status": "success",
        "data": {
            "email": user_email,
            "subscriptions": subscriptions,
            "current": subscriptions[0] if subscriptions else {},
            "available_accounts": available_accounts,
        },
    }


def build_profile_from_brand_responses(
    brand_responses: Sequence[tuple[str, Mapping[str, Any]]],
    available_accounts: list[dict[str, Any]],
) -> dict[str, Any]:
    """Pure aggregation from already-fetched (brand, profile_json) pairs."""
    agg: dict[str, dict[str, Any]] = {}
    user_email = ""
    for brand, data in brand_responses:
        user_email = merge_brand_profile_data(brand, data, agg, user_email)
    subscriptions_list = list(agg.values())
    return build_profile_result(
        user_email=user_email,
        subscriptions=subscriptions_list,
        available_accounts=available_accounts,
    )


def fetch_and_build_profile(
    *,
    brands: Sequence[str],
    make_request: Callable[..., Any],
    request: Request,
    ctx: SessionContext,
    req_ident: str,
    account_ctx: Mapping[str, Any],
    accounts: Mapping[str, Any],
) -> dict[str, Any]:
    """Fetch getProfile per brand and build the cached profile payload."""
    available_accounts = build_available_accounts(accounts, req_ident)
    agg: dict[str, dict[str, Any]] = {}
    user_email = ""

    for brand in brands:
        try:
            r = make_request(
                request=request,
                ctx=ctx,
                method="GET",
                url=simworld_url(brand, "user/getProfile"),
                account_id=req_ident,
                account_context=account_ctx,
            )
            if r and r.status_code == 200:
                data = r.json()
                user_email = merge_brand_profile_data(brand, data, agg, user_email)
        except Exception as exc:
            logger.error("Err parsing %s: %s", brand, exc)
            continue

    subscriptions_list = list(agg.values())
    return build_profile_result(
        user_email=user_email,
        subscriptions=subscriptions_list,
        available_accounts=available_accounts,
    )
