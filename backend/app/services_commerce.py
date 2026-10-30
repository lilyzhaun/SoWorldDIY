"""Commerce helpers: wallet balance parse and plans cache load."""

from __future__ import annotations

import json
import logging
from collections.abc import Mapping
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from typing import Final, Literal, NotRequired, TypedDict

from .brand import ensure_within_cache_dir
from .idempotency import UpstreamWriteUncertain
from .schemas.requests import CmnPurchaseRequest, PurchaseRequest
from .upstream_urls import (
    SIMWORLD_PAYMENT_FINISHED,
    SIMWORLD_WEB_MAIN,
    THREE_DIY_PAYMENT_FINISHED,
)

logger = logging.getLogger(__name__)

BASE_NEW_LINE_OFFER: Final = "H3OF00000000001"


class PurchaseResult(TypedDict):
    status: Literal["success", "error"]
    paymentUrl: NotRequired[str]


def parse_purchase_result(data: object) -> PurchaseResult:
    """Follow SIMWorld's payment result codes, not the presence of a redirect."""
    if not isinstance(data, dict):
        raise UpstreamWriteUncertain("Invalid purchase result")
    code = data.get("code")
    # The upstream checkout handles 1 as direct success (e.g. wallet-only),
    # 2 as failure, 3/4/5 as redirects, and 9 as pending.
    if type(code) is int:
        if code == 1:
            return {"status": "success"}
        if code == 2:
            return {"status": "error"}
    payment_url = data.get("paymentUrl")
    if (
        (code is None or (type(code) is int and code in (3, 4, 5)))
        and isinstance(payment_url, str)
        and payment_url.strip()
    ):
        return {"status": "success", "paymentUrl": payment_url}
    raise UpstreamWriteUncertain("Missing or pending payment result")


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


class CmnPurchaseOfferPayload(TypedDict):
    offerId: str | int | None
    quantity: int


class CmnPurchaseSubscriptionPayload(TypedDict, total=False):
    msisdn: str
    lang: str
    subscriptionId: str | int | None
    offers: list[CmnPurchaseOfferPayload]
    walletPayment: dict[str, float]


class CmnPurchaseOrderPayload(TypedDict):
    channel: str
    autoPayFlag: bool
    pmt: PurchasePaymentPayload
    orderSubscription: CmnPurchaseSubscriptionPayload


class CmnPurchasePayload(TypedDict):
    fUrl: str
    purchaseType: str
    accessPurchaseKey: str | None
    order: CmnPurchaseOrderPayload


@dataclass(frozen=True, slots=True)
class CmnPurchasePayloadResult:
    payload: CmnPurchasePayload
    payable_amount: float


def build_cmn_purchase_payload(
    body: CmnPurchaseRequest,
    access_key: str | None,
) -> CmnPurchasePayloadResult:
    """Build the upstream payload for a CMN number purchase."""
    txn = float(body.txnAmount)
    payable_amount = float(
        max(Decimal(0), Decimal(str(body.price)) - Decimal(str(txn))).quantize(
            Decimal("0.01")
        )
    )
    payment: PurchasePaymentPayload = {"amnt": payable_amount}
    if payable_amount > 0:
        payment.update({"lang": "tc", "type": body.paymentType})

    subscription: CmnPurchaseSubscriptionPayload = {
        "msisdn": str(body.selectedNumber),
        "lang": "tc",
        "subscriptionId": body.subscriptionId,
        "offers": [{"offerId": body.offerId, "quantity": 1}],
    }
    if txn > 0:
        subscription["walletPayment"] = {"txnAmount": txn}

    payload: CmnPurchasePayload = {
        "fUrl": SIMWORLD_PAYMENT_FINISHED,
        "purchaseType": "CMN_ONLY",
        "accessPurchaseKey": access_key,
        "order": {
            "channel": "ONLINE",
            "autoPayFlag": False,
            "pmt": payment,
            "orderSubscription": subscription,
        },
    }
    return CmnPurchasePayloadResult(
        payload=payload,
        payable_amount=payable_amount,
    )


def build_plan_purchase_payload(
    body: PurchaseRequest,
    access_key: str | None,
) -> PlanPurchasePayloadResult:
    """Build the upstream payload for normal or new-line plan purchases."""
    txn = float(body.txnAmount)
    payable_amount = float(
        max(Decimal(0), Decimal(str(body.price)) - Decimal(str(txn))).quantize(
            Decimal("0.01")
        )
    )
    payment: PurchasePaymentPayload = {"amnt": payable_amount}
    if payable_amount > 0:
        payment.update({"lang": "tc", "type": body.paymentType})

    if body.new_line:
        new_line_offers: list[PurchaseOfferPayload] = [
            {
                "offerId": BASE_NEW_LINE_OFFER,
                "quantity": 1,
                "autoRenewFlag": False,
            }
        ]
        new_line_offers.extend(
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
                "offers": new_line_offers,
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
        normal_offers: list[PurchaseOfferPayload] = [
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
            "offers": normal_offers,
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


def _wallet_amount(value: object) -> float:
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


def parse_wallet_balance(data: object) -> float:
    """Return max amount from WalletBalances list payload, else 0."""
    if not isinstance(data, list) or not data:
        return 0.0
    amounts: list[float] = []
    for item in data:
        if not isinstance(item, Mapping):
            raise TypeError(
                f"wallet balance item must be a mapping, got {type(item).__name__}"
            )
        if "amount" not in item:
            continue
        amounts.append(_wallet_amount(item.get("amount", 0)))
    return max(amounts, default=0.0)


def load_plans_from_cache(
    cache_file: Path,
    *,
    cache_root: Path,
    brand: str | None = None,
) -> dict[str, object] | None:
    """Load plans JSON from disk after verifying path containment in cache_root.

    Missing file returns None without logging (caller decides next step).
    Parse failures log a warning and return None.
    """
    ensure_within_cache_dir(cache_file, cache_root)
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
