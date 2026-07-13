"""Unit tests for pure service helpers (no ASGI / monkeypatch seams)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.requests import CmnPurchaseRequest, PurchaseItem, PurchaseRequest
from app.services_commerce import (
    build_cmn_purchase_payload,
    build_plan_purchase_payload,
    load_plans_from_cache,
    parse_wallet_balance,
)
from app.upstream_urls import SIMWORLD_PAYMENT_FINISHED


def test_parse_wallet_balance_max_amount() -> None:
    assert parse_wallet_balance([{"amount": 5}, {"amount": 88.5}]) == 88.5
    assert parse_wallet_balance([]) == 0.0
    assert parse_wallet_balance(None) == 0.0
    assert parse_wallet_balance({"amount": 1}) == 0.0
    assert parse_wallet_balance([{"nope": 1}, {"amount": 3}]) == 3.0


def test_parse_wallet_balance_malformed_element_raises() -> None:
    with pytest.raises(TypeError):
        parse_wallet_balance([1, {"amount": 3}])
    with pytest.raises(TypeError):
        parse_wallet_balance(["amount"])
    with pytest.raises(TypeError):
        parse_wallet_balance(["not-an-amount"])


def test_load_plans_from_cache_ok_and_missing(tmp_path: Path) -> None:
    missing = tmp_path / "nope.json"
    assert load_plans_from_cache(missing) is None

    good = tmp_path / "plans_THREE.json"
    payload = {"status": "success", "plans": [{"offerId": "X"}]}
    good.write_text(json.dumps(payload), encoding="utf-8")
    assert load_plans_from_cache(good) == payload

    bad = tmp_path / "bad.json"
    bad.write_text("{not-json", encoding="utf-8")
    assert load_plans_from_cache(bad) is None


def test_build_plan_purchase_payload_normal_flow() -> None:
    body = PurchaseRequest(
        subscriptionId="sub-1",
        items=[
            PurchaseItem(offerId="OFF1", quantity=2),
            PurchaseItem(offerId="OFF2", quantity=1),
        ],
        price=100,
        txnAmount=30,
        paymentType="ALCN",
    )

    result = build_plan_purchase_payload(body, "KEY")

    assert result.payable_amount == 70.0
    assert result.payload == {
        "fUrl": "https://simworld.net/SIMworld/main/tc",
        "purchaseType": "SOSIM_VAS",
        "accessPurchaseKey": "KEY",
        "order": {
            "channel": "ONLINE",
            "autoPayFlag": False,
            "lang": "tc",
            "pmt": {"amnt": 70.0, "lang": "tc", "type": "ALCN"},
            "orderSubscriptions": [
                {
                    "lang": "tc",
                    "subscriptionId": "sub-1",
                    "offers": [
                        {"offerId": "OFF1", "quantity": 2, "autoRenewFlag": False},
                        {"offerId": "OFF2", "quantity": 1, "autoRenewFlag": False},
                    ],
                    "walletPayment": {"txnAmount": 30.0},
                }
            ],
        },
    }


def test_build_plan_purchase_payload_new_line_exact_shape_and_no_mutation() -> None:
    body = PurchaseRequest(
        subscriptionId="sub-1",
        new_line=True,
        items=[
            PurchaseItem(offerId="VAS1", quantity=1),
            PurchaseItem(offerId="H3OF00000000001", quantity=99),
            PurchaseItem(offerId="VAS2", quantity=3),
        ],
        price=10,
        txnAmount=20,
        paymentType="CARD",
    )
    before = body.model_dump()

    result = build_plan_purchase_payload(body, None)

    assert body.model_dump() == before
    assert result.payable_amount == 0.0
    order = result.payload["order"]
    subscription = order.get("orderSubscription")
    assert subscription is not None
    offers = subscription["offers"]
    assert offers == [
        {"offerId": "H3OF00000000001", "quantity": 1, "autoRenewFlag": False},
        {"offerId": "VAS1", "quantity": 1, "autoRenewFlag": False},
        {"offerId": "VAS2", "quantity": 3, "autoRenewFlag": False},
    ]
    assert order.get("pmt") == {"amnt": 0.0}
    assert "walletPayment" not in order


def test_build_cmn_purchase_payload_external_payment_and_wallet() -> None:
    body = CmnPurchaseRequest(
        subscriptionId="sub-1",
        selectedNumber="85298765432",
        offerId="CMN-OFFER",
        price=100,
        txnAmount=30,
        paymentType="ALCN",
    )
    before = body.model_dump()

    result = build_cmn_purchase_payload(body, "KEY")

    assert body.model_dump() == before
    assert result.payable_amount == 70.0
    assert result.payload == {
        "fUrl": SIMWORLD_PAYMENT_FINISHED,
        "purchaseType": "CMN_ONLY",
        "accessPurchaseKey": "KEY",
        "order": {
            "channel": "ONLINE",
            "autoPayFlag": False,
            "pmt": {"amnt": 70.0, "lang": "tc", "type": "ALCN"},
            "orderSubscription": {
                "msisdn": "85298765432",
                "lang": "tc",
                "subscriptionId": "sub-1",
                "offers": [{"offerId": "CMN-OFFER", "quantity": 1}],
                "walletPayment": {"txnAmount": 30.0},
            },
        },
    }


def test_build_cmn_purchase_payload_clamps_amount_and_omits_external_payment() -> None:
    body = CmnPurchaseRequest(
        subscriptionId="sub-2",
        selectedNumber=123,
        offerId="CMN-OFFER-2",
        price=10,
        txnAmount=20,
        paymentType="CARD",
    )

    result = build_cmn_purchase_payload(body, None)

    assert result.payable_amount == 0.0
    assert result.payload["order"]["pmt"] == {"amnt": 0.0}
    assert "walletPayment" in result.payload["order"]["orderSubscription"]
    assert result.payload["order"]["orderSubscription"]["walletPayment"] == {
        "txnAmount": 20.0
    }
