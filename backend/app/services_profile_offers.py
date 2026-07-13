"""Profile offer aggregation: pure helpers for activeOffers construction."""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from typing import TypedDict


class UsageEntry(TypedDict):
    name: object
    unit: object
    total: float
    remain: float
    percent: float
    canTransfer: object
    minTransfer: object
    balanceResourceId: object
    productFamily: str
    userOfferId: object


class ActiveOffer(TypedDict):
    offerId: object
    name: object
    desc: object
    price: object
    endDate: str
    isVoWifi: bool
    planStatus: object
    usage: list[UsageEntry]


class DTOAgg(TypedDict):
    usages: list[UsageEntry]
    dates: list[str]
    is_vowifi: bool


def safe_date_str(val: object) -> str:
    if val and isinstance(val, str) and "T" in val:
        return val.split("T")[0]
    return ""


def fuzzy_time_key(val: object) -> object:
    if val and isinstance(val, str) and len(val) >= 16:
        return val[:16]
    return val


def require_mapping_list(value: object) -> list[Mapping[str, object]]:
    """Require a list of mappings; malformed containers raise TypeError."""
    if not isinstance(value, list):
        raise TypeError(f"expected list of mappings, got {type(value).__name__}")
    result: list[Mapping[str, object]] = []
    for index, item in enumerate(value):
        if not isinstance(item, Mapping):
            raise TypeError(
                f"sequence element {index} must be a mapping, got {type(item).__name__}"
            )
        result.append(item)
    return result


def _to_float(value: object) -> float:
    if isinstance(value, bool):
        return float(value)
    if isinstance(value, int):
        return float(value)
    if isinstance(value, float):
        return value
    if isinstance(value, str):
        return float(value)
    raise TypeError(
        f"float() argument must be a string or a real number, not '{type(value).__name__}'"
    )


def _product_family(prod: Mapping[str, object]) -> str:
    spec_type = str(prod.get("productSpecType", "")).upper()
    if "VOICE" in spec_type:
        return "VOICE"
    if "DATA" in spec_type:
        return "DATA"
    return str(prod.get("productFamily", "DATA"))


def _is_vowifi_product(prod: Mapping[str, object]) -> bool:
    name = str(prod.get("productName", "")).upper().replace(" ", "")
    return "VOWIFI" in name


def _build_usage_list(
    raw_products: Sequence[Mapping[str, object]],
    *,
    offer_transfer: bool,
    current_offer_id: object,
) -> list[UsageEntry]:
    usage_list: list[UsageEntry] = []
    for prod in raw_products:
        prod_transfer = prod.get("transferAllowed", False)
        min_quota = prod.get("minTransferQuota", 0)
        p_family = _product_family(prod)
        for bal in require_mapping_list(prod.get("matrixxBalanceInfos", [])):
            if bal.get("unit") in ["Money", "HKD"]:
                continue
            total = _to_float(bal.get("grantAmount", 0))
            remain = _to_float(bal.get("amount", 0))
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


def build_active_offers(
    raw_offers: Sequence[Mapping[str, object]],
) -> list[ActiveOffer]:
    """Aggregate subscriptionOffers into the activeOffers list for one SIM."""
    dto_sender_map: dict[object, object] = {}
    for offer in raw_offers:
        if offer.get("offerSubType") == "DTO":
            sender = offer.get("transferFromMsisdn")
            end_date = offer.get("endDate")
            if sender and end_date:
                dto_sender_map[fuzzy_time_key(end_date)] = sender

    active_offers: list[ActiveOffer] = []
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

        raw_products = require_mapping_list(offer.get("subscriptionProducts", []))
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
                "endDate": max(dto_data_agg["dates"]) if dto_data_agg["dates"] else "",
                "isVoWifi": dto_data_agg["is_vowifi"],
                "planStatus": "ACTIVE",
                "usage": dto_data_agg["usages"],
            }
        )
    return active_offers
