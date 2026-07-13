"""Commerce helpers: wallet balance parse and plans cache load."""

from __future__ import annotations

import json
import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, TypedDict

from .schemas.requests import PurchaseRequest
from .upstream_urls import SIMWORLD_WEB_MAIN, THREE_DIY_PAYMENT_FINISHED

logger = logging.getLogger(__name__)

BASE_NEW_LINE_OFFER: Final = "H3OF00000000001"


class PurchaseOfferPayload(TypedDict):
    offerId: str
    quantity: int
    autoRenewFlag: bool


class PurchasePaymentPayload(TypedDict, total=False):
    amnt: float
    lang: str
    type: str


class NormalPurchaseSubscriptionPayload(TypedDict, total=False):
    lang: str
    subscriptionId: str | None
    offers: list[PurchaseOfferPayload]
    walletPayment: dict[str, float]


class NormalPurchaseOrderPayload(TypedDict):
    channel: str
    autoPayFlag: bool
    lang: str
    pmt: PurchasePaymentPayload
    orderSubscriptions: list[NormalPurchaseSubscriptionPayload]


class NewLinePurchaseSubscriptionPayload(TypedDict):
    lang: str
    offers: list[PurchaseOfferPayload]
    promoOptOuts: list[str]
    simType: str


class NewLinePurchaseOrderPayload(TypedDict):
    channel: str
    autoPayFlag: bool
    pmt: PurchasePaymentPayload
    orderSubscription: NewLinePurchaseSubscriptionPayload


class PlanPurchaseOrderPayload(TypedDict, total=False):
    channel: str
    autoPayFlag: bool
    lang: str
    pmt: PurchasePaymentPayload
    orderSubscriptions: list[NormalPurchaseSubscriptionPayload]
    orderSubscription: NewLinePurchaseSubscriptionPayload


class PlanPurchasePayload(TypedDict):
    fUrl: str
    accessPurchaseKey: str | None
    purchaseType: str
    order: PlanPurchaseOrderPayload


@dataclass(frozen=True, slots=True)
class PlanPurchasePayloadResult:
    payload: PlanPurchasePayload
    payable_amount: float


def build_plan_purchase_payload(
    body: PurchaseRequest,
    access_key: str | None,
) -> PlanPurchasePayloadResult:
    """Build the upstream payload for normal or new-line plan purchases."""
    txn = float(body.txnAmount)
    payable_amount = max(0.0, float(body.price) - txn)
    payment: PurchasePaymentPayload = {"amnt": payable_amount}
    if payable_amount > 0:
        payment.update({"lang": "tc", "type": body.paymentType})

    if body.new_line:
        offers: list[PurchaseOfferPayload] = [
            {
                "offerId": BASE_NEW_LINE_OFFER,
                "quantity": 1,
                "autoRenewFlag": False,
            }
        ]
        offers.extend(
            {
                "offerId": item.offerId,
                "quantity": int(item.quantity),
                "autoRenewFlag": False,
            }
            for item in body.items
            if item.offerId != BASE_NEW_LINE_OFFER
        )
        new_line_order: PlanPurchaseOrderPayload = {
            "channel": "GLOBAL_ESIM",
            "autoPayFlag": False,
            "pmt": payment,
            "orderSubscription": {
                "lang": "tc",
                "offers": offers,
                "promoOptOuts": [],
                "simType": "ESIM",
            },
        }
        payload: PlanPurchasePayload = {
            "fUrl": THREE_DIY_PAYMENT_FINISHED,
            "accessPurchaseKey": access_key,
            "purchaseType": "PREPAID_DIY",
            "order": new_line_order,
        }
    else:
        offers: list[PurchaseOfferPayload] = [
            {
                "offerId": item.offerId,
                "quantity": int(item.quantity),
                "autoRenewFlag": False,
            }
            for item in body.items
        ]
        subscription: NormalPurchaseSubscriptionPayload = {
            "lang": "tc",
            "subscriptionId": body.subscriptionId,
            "offers": offers,
        }
        if txn > 0:
            subscription["walletPayment"] = {"txnAmount": txn}
        normal_order: PlanPurchaseOrderPayload = {
            "channel": "ONLINE",
            "autoPayFlag": False,
            "lang": "tc",
            "pmt": payment,
            "orderSubscriptions": [subscription],
        }
        payload = {
            "fUrl": SIMWORLD_WEB_MAIN,
            "purchaseType": "SOSIM_VAS",
            "accessPurchaseKey": access_key,
            "order": normal_order,
        }

    return PlanPurchasePayloadResult(payload=payload, payable_amount=payable_amount)


def parse_wallet_balance(data: Any) -> float:
    """Return max amount from WalletBalances list payload, else 0."""
    if isinstance(data, list) and data:
        return max(
            float(item.get("amount", 0)) for item in data if "amount" in item
        )
    return 0.0


def load_plans_from_cache(
    cache_file: Path,
    *,
    brand: str | None = None,
) -> dict[str, Any] | None:
    """Load plans JSON from disk; log and return None on parse failure.

    Missing file returns None without logging (caller decides next step).
    """
    if not cache_file.exists():
        return None
    try:
        loaded = json.loads(cache_file.read_text(encoding="utf-8"))
    except Exception:
        logger.warning(
            "plans cache parse failed brand=%s path=%s",
            brand,
            cache_file,
            exc_info=True,
        )
        return None
    if isinstance(loaded, dict):
        return loaded
    return None
