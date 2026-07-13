"""Commerce helpers: wallet balance, plans cache, purchase payloads."""

from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any

from .schemas import CmnPurchaseRequest, PurchaseItem, PurchaseRequest
from .upstream_urls import (
    SIMWORLD_PAYMENT_FINISHED,
    SIMWORLD_WEB_MAIN,
    THREE_DIY_PAYMENT_FINISHED,
)

logger = logging.getLogger(__name__)

DIY_BASE_OFFER_ID = "H3OF00000000001"


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


def build_payment_block(price: float, txn_amount: float, payment_type: str) -> dict[str, Any]:
    """Build the upstream ``pmt`` object for a purchase."""
    pmt: dict[str, Any] = {"amnt": max(0.0, float(price) - float(txn_amount))}
    if pmt["amnt"] > 0:
        pmt.update({"lang": "tc", "type": payment_type})
    return pmt


def _items_to_offers(items: list[PurchaseItem]) -> list[dict[str, Any]]:
    return [
        {
            "offerId": item.offerId,
            "quantity": int(item.quantity),
            "autoRenewFlag": False,
        }
        for item in items
    ]


def build_plan_purchase_payload(
    body: PurchaseRequest,
    *,
    access_key: Any,
) -> dict[str, Any]:
    """Assemble createPurchase payload for normal VAS or new-line DIY flow."""
    txn = float(body.txnAmount)
    pmt = build_payment_block(float(body.price), txn, body.paymentType)

    if body.new_line:
        offers_payload = [
            {
                "offerId": DIY_BASE_OFFER_ID,
                "quantity": 1,
                "autoRenewFlag": False,
            },
        ]
        for item in body.items:
            if item.offerId != DIY_BASE_OFFER_ID:
                offers_payload.append(
                    {
                        "offerId": item.offerId,
                        "quantity": int(item.quantity),
                        "autoRenewFlag": False,
                    }
                )
        return {
            "fUrl": THREE_DIY_PAYMENT_FINISHED,
            "accessPurchaseKey": access_key,
            "purchaseType": "PREPAID_DIY",
            "order": {
                "channel": "GLOBAL_ESIM",
                "autoPayFlag": False,
                "pmt": pmt,
                "orderSubscription": {
                    "lang": "tc",
                    "offers": offers_payload,
                    "promoOptOuts": [],
                    "simType": "ESIM",
                },
            },
        }

    offers_payload = _items_to_offers(list(body.items))
    sub_payload: dict[str, Any] = {
        "lang": "tc",
        "subscriptionId": body.subscriptionId,
        "offers": offers_payload,
    }
    if txn > 0:
        sub_payload["walletPayment"] = {"txnAmount": txn}
    return {
        "fUrl": SIMWORLD_WEB_MAIN,
        "purchaseType": "SOSIM_VAS",
        "accessPurchaseKey": access_key,
        "order": {
            "channel": "ONLINE",
            "autoPayFlag": False,
            "lang": "tc",
            "pmt": pmt,
            "orderSubscriptions": [sub_payload],
        },
    }


def build_cmn_purchase_payload(
    body: CmnPurchaseRequest,
    *,
    access_key: Any,
) -> tuple[dict[str, Any], float]:
    """Assemble CMN createPurchase payload and external payment amount."""
    txn = float(body.txnAmount)
    pmt_amt = max(0.0, float(body.price) - txn)
    pmt: dict[str, Any] = {"amnt": pmt_amt}
    order_sub: dict[str, Any] = {
        "msisdn": str(body.selectedNumber),
        "lang": "tc",
        "subscriptionId": body.subscriptionId,
        "offers": [{"offerId": body.offerId, "quantity": 1}],
    }
    if pmt_amt > 0:
        pmt.update({"lang": "tc", "type": body.paymentType})
    if txn > 0:
        order_sub["walletPayment"] = {"txnAmount": txn}

    payload = {
        "fUrl": SIMWORLD_PAYMENT_FINISHED,
        "purchaseType": "CMN_ONLY",
        "accessPurchaseKey": access_key,
        "order": {
            "channel": "ONLINE",
            "autoPayFlag": False,
            "pmt": pmt,
            "orderSubscription": order_sub,
        },
    }
    return payload, pmt_amt
