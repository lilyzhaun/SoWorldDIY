"""Profile aggregation: pure helpers + brand fetch/build for /api/profile."""

from __future__ import annotations

import logging
from collections.abc import Mapping, MutableMapping, Sequence
from typing import TypedDict

from fastapi import Request

from .services_profile_offers import (
    ActiveOffer,
    build_active_offers,
    fuzzy_time_key,
    require_mapping_list,
    safe_date_str,
)
from .session_store import SessionContext
from .upstream import Make3hkRequestFn
from .upstream_urls import simworld_url

logger = logging.getLogger(__name__)

__all__ = [
    "ActiveOffer",
    "AvailableAccount",
    "ProfileResult",
    "SubscriptionEntry",
    "build_active_offers",
    "build_available_accounts",
    "build_profile_from_brand_responses",
    "build_profile_result",
    "build_subscription_entry",
    "fetch_and_build_profile",
    "fuzzy_time_key",
    "merge_brand_profile_data",
    "safe_date_str",
]


class AvailableAccount(TypedDict):
    identifier: str
    active: bool
    subBrand: object


class SubscriptionEntry(TypedDict):
    mobile: object
    activationDate: str
    subsEndDate: str
    subscriptionId: object
    brand: str
    iccid: object
    status: object
    activeOffers: list[ActiveOffer]


class ProfileData(TypedDict):
    email: str
    subscriptions: list[SubscriptionEntry]
    current: SubscriptionEntry | dict[str, object]
    available_accounts: list[AvailableAccount]


class ProfileResult(TypedDict):
    status: str
    data: ProfileData


def build_available_accounts(
    accounts: Mapping[str, object],
    req_ident: str,
) -> list[AvailableAccount]:
    available: list[AvailableAccount] = []
    for key, val in accounts.items():
        if not isinstance(val, Mapping):
            raise TypeError(
                f"account entry must be a mapping, got {type(val).__name__}"
            )
        available.append(
            {
                "identifier": key,
                "active": str(key) == str(req_ident),
                "subBrand": val.get("sub_brand", "THREE"),
            }
        )
    return available


def build_subscription_entry(
    sub: Mapping[str, object],
    brand: str,
) -> SubscriptionEntry | None:
    """Turn one upstream subscription into the profile subscription dict."""
    mobile = sub.get("primaryMsisdn")
    if not mobile:
        return None
    raw_offers = require_mapping_list(sub.get("subscriptionOffers", []))
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
    data: Mapping[str, object],
    agg: dict[str, SubscriptionEntry],
    user_email: str,
) -> str:
    """Merge one brand getProfile JSON into agg; return updated user_email."""
    email = user_email
    if not email and data.get("email"):
        email = str(data.get("email", ""))
    for sub in require_mapping_list(data.get("subscriptions", [])):
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
    subscriptions: list[SubscriptionEntry],
    available_accounts: list[AvailableAccount],
) -> ProfileResult:
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
    brand_responses: Sequence[tuple[str, Mapping[str, object]]],
    available_accounts: list[AvailableAccount],
) -> ProfileResult:
    """Pure aggregation from already-fetched (brand, profile_json) pairs."""
    agg: dict[str, SubscriptionEntry] = {}
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
    make_request: Make3hkRequestFn,
    request: Request,
    ctx: SessionContext,
    req_ident: str,
    account_ctx: MutableMapping[str, object],
    accounts: Mapping[str, object],
) -> ProfileResult:
    """Fetch getProfile per brand and build the cached profile payload."""
    available_accounts = build_available_accounts(accounts, req_ident)
    agg: dict[str, SubscriptionEntry] = {}
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
                if not isinstance(data, Mapping):
                    raise TypeError(
                        f"getProfile payload must be a mapping, got {type(data).__name__}"
                    )
                user_email = merge_brand_profile_data(brand, data, agg, user_email)
        except Exception as exc:
            logger.error(
                "Profile parse failed brand=%s error_class=%s",
                brand,
                type(exc).__name__,
            )
            continue

    subscriptions_list = list(agg.values())
    return build_profile_result(
        user_email=user_email,
        subscriptions=subscriptions_list,
        available_accounts=available_accounts,
    )
