from __future__ import annotations

import json
import logging
from collections.abc import Callable, Mapping
from typing import Any, Protocol, runtime_checkable

import requests

from .brand import InvalidBrandError, parse_brand, plans_cache_path
from .cache_store import profile_cache_key
from .runtime import BASE_HEADERS, PLANS_CACHE_DIR, PROXIES, plans_refresh_lock
from .session_store import SessionContext
from .upstream_urls import three_offer_url

logger = logging.getLogger(__name__)


class FetchPlansBackgroundFn(Protocol):
    def __call__(
        self,
        sub_brand: str,
        cookies: Mapping[str, object],
        user_agent: str | None,
    ) -> None: ...


@runtime_checkable
class ServiceDepsProtocol(Protocol):
    """Read-only dependency surface for service helpers.

    Members are ``@property`` so adapters like ``MainDepsAdapter`` (which
    re-read live ``main`` seams for monkeypatch targets) structurally satisfy
    this protocol without mutable attribute assignment.
    """

    @property
    def get_cache(self) -> Callable[[str], Any | None]: ...

    @property
    def get_account_context(
        self,
    ) -> Callable[[SessionContext, str | None], dict[str, Any] | None]: ...

    @property
    def plans_refreshing(self) -> set[str]: ...

    @property
    def get_isolated_session(self) -> Callable[[], requests.Session]: ...


_service_deps_provider: Callable[[], ServiceDepsProtocol] | None = None


def configure_service_deps(provider: Callable[[], ServiceDepsProtocol]) -> None:
    global _service_deps_provider
    _service_deps_provider = provider


def _deps() -> ServiceDepsProtocol:
    if _service_deps_provider is None:
        raise RuntimeError("service deps not configured; call configure_service_deps")
    return _service_deps_provider()


def get_brand_by_sub_id(
    ctx: SessionContext,
    sub_id: str | None,
    account_id: str | None,
) -> str:
    d = _deps()
    if account_id:
        data = d.get_cache(profile_cache_key(ctx.sid, account_id))
        if data and isinstance(data, dict):
            subscriptions = data.get("data", {}).get("subscriptions", [])
            for sub in subscriptions:
                if str(sub.get("subscriptionId")) == str(sub_id):
                    return str(sub.get("brand", "THREE"))

    account = d.get_account_context(ctx, account_id)
    if account:
        return str(account.get("sub_brand", "THREE"))
    return "THREE"


def fetch_and_save_plans_background(
    sub_brand: str, cookies: dict[str, Any], user_agent: str | None
) -> None:
    try:
        brand = parse_brand(sub_brand)
        file_path = plans_cache_path(PLANS_CACHE_DIR, brand)
    except InvalidBrandError:
        logger.warning("Background plan fetch rejected invalid brand=%r", sub_brand)
        return

    d = _deps()
    with plans_refresh_lock:
        if brand in d.plans_refreshing:
            return
        d.plans_refreshing.add(brand)
    try:
        url = three_offer_url(brand, "offer/getPlanOffers/")
        headers = dict(BASE_HEADERS)
        if user_agent:
            headers["User-Agent"] = user_agent
        with d.get_isolated_session() as s:
            s.cookies.update(cookies)
            r = s.get(url, headers=headers, proxies=PROXIES, timeout=15)
            if r.status_code == 200:
                vas_plans: list[dict[str, Any]] = []
                for offer in r.json().get("offers", []):
                    if offer.get("offerType") != "VAS":
                        continue
                    subtype = str(offer.get("offerSubType", "")).upper()
                    if "LOCAL" in subtype:
                        category = "LOCAL"
                    elif "TRAVEL" in subtype or "ROAMING" in subtype:
                        category = "TRAVEL"
                    elif "VOICE" in subtype:
                        category = "VOICE"
                    else:
                        category = "OTHER"

                    is_vowifi = any(
                        "VOWIFI"
                        in str(p.get("productName", "")).upper().replace(" ", "")
                        for p in offer.get("products", [])
                    )
                    vas_plans.append(
                        {
                            "offerId": offer["offerId"],
                            "name": offer.get("offerNameChi", offer.get("offerName")),
                            "price": offer["offerPrice"],
                            "validity": f"{offer['offerPeriod']} {offer['offerPeriodTerm']}",
                            "desc": offer.get("offerDescChi", offer.get("offerDesc")),
                            "isVoWifi": is_vowifi,
                            "category": category,
                        }
                    )
                result = {
                    "status": "success",
                    "plans": sorted(vas_plans, key=lambda x: x["price"]),
                }
                plans_cache_path(PLANS_CACHE_DIR, brand)
                file_path.write_text(
                    json.dumps(result, ensure_ascii=False), encoding="utf-8"
                )
                logger.info("Plans updated for %s", brand)
    except Exception as exc:
        logger.error(
            "Background plan fetch failed brand=%s error_class=%s",
            brand,
            type(exc).__name__,
        )
    finally:
        with plans_refresh_lock:
            d.plans_refreshing.discard(brand)
