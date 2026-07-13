"""Unit tests for pure service helpers (no ASGI / monkeypatch seams)."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from app.schemas.requests import (
    CmnPurchaseRequest,
    PurchaseItem,
    PurchaseRequest,
    TransferRequest,
)
from app.services_commerce import (
    build_cmn_purchase_payload,
    build_plan_purchase_payload,
    load_plans_from_cache,
    parse_wallet_balance,
)
from app.services_profile import (
    build_active_offers,
    build_available_accounts,
    build_profile_from_brand_responses,
    build_subscription_entry,
    fuzzy_time_key,
    merge_brand_profile_data,
    safe_date_str,
)
from app.services_transfer import (
    assemble_transfer_payload,
    select_dto_offer,
    select_transfer_product_id,
)
from app.upstream_urls import SIMWORLD_PAYMENT_FINISHED


def test_transfer_request_accepts_numeric_coercion_inputs() -> None:
    body = TransferRequest.model_validate(
        {
            "account_id": "a@b.com",
            "subscriptionId": 1001,
            "productFamily": "DATA",
            "sourceMsisdn": 85211112222,
            "targetMsisdn": "85233334444",
            "userOfferId": "UO",
            "balanceResourceId": "9",
            "unit": "MB",
            "amount": "500.5",
        }
    )
    assert body.subscriptionId == 1001
    assert body.sourceMsisdn == 85211112222
    assert body.balanceResourceId == "9"
    assert body.amount == "500.5"
    assert int(body.balanceResourceId) == 9
    assert float(body.amount) == 500.5


def test_build_available_accounts_marks_active() -> None:
    accounts = {
        "a@b.com": {"sub_brand": "THREE"},
        "b@c.com": {"sub_brand": "SOSIM"},
    }
    result = build_available_accounts(accounts, "b@c.com")
    assert result == [
        {"identifier": "a@b.com", "active": False, "subBrand": "THREE"},
        {"identifier": "b@c.com", "active": True, "subBrand": "SOSIM"},
    ]


def test_safe_date_str_splits_iso() -> None:
    assert safe_date_str("2024-01-01T12:00:00") == "2024-01-01"
    assert safe_date_str("no-t-here") == ""
    assert safe_date_str(None) == ""
    assert safe_date_str(123) == ""


def test_fuzzy_time_key_truncates() -> None:
    assert fuzzy_time_key("2024-01-01T12:34:56Z") == "2024-01-01T12:34"
    assert fuzzy_time_key("short") == "short"
    assert fuzzy_time_key(None) is None


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


def test_select_dto_offer_malformed_container_raises() -> None:
    with pytest.raises(TypeError):
        select_dto_offer({"offerSubType": "DTO"})
    with pytest.raises(TypeError):
        select_dto_offer("DTO")
    with pytest.raises(TypeError):
        select_dto_offer([{"offerSubType": "OTHER"}, "not-a-mapping"])


def test_select_dto_offer_valid_empty_or_no_dto_returns_none() -> None:
    assert select_dto_offer([]) is None
    assert select_dto_offer([{"offerSubType": "OTHER"}]) is None


def test_select_transfer_product_id_malformed_products_raises() -> None:
    with pytest.raises(TypeError):
        select_transfer_product_id({"products": "bad"}, "DATA")
    with pytest.raises(TypeError):
        select_transfer_product_id(
            {"products": [{"productId": "P", "productFamily": "DATA"}, 1]},
            "DATA",
        )
    with pytest.raises(KeyError):
        select_transfer_product_id({}, "DATA")


def test_build_active_offers_malformed_products_raises() -> None:
    with pytest.raises(TypeError):
        build_active_offers(
            [
                {
                    "offerId": "OFF1",
                    "offerType": "VAS",
                    "offerSubType": "LOCAL",
                    "planStatus": "ACTIVE",
                    "subscriptionProducts": "not-a-list",
                }
            ]
        )
    with pytest.raises(TypeError):
        build_active_offers(
            [
                {
                    "offerId": "OFF1",
                    "offerType": "VAS",
                    "offerSubType": "LOCAL",
                    "planStatus": "ACTIVE",
                    "subscriptionProducts": ["not-a-mapping"],
                }
            ]
        )


def test_merge_brand_profile_malformed_subscriptions_raises() -> None:
    with pytest.raises(TypeError):
        merge_brand_profile_data(
            "THREE",
            {"email": "a@b.com", "subscriptions": "bad"},
            {},
            "",
        )
    with pytest.raises(TypeError):
        build_subscription_entry(
            {
                "primaryMsisdn": "8521",
                "subscriptionOffers": {"offerId": "x"},
            },
            "THREE",
        )


def test_build_available_accounts_malformed_entry_raises() -> None:
    with pytest.raises(TypeError):
        build_available_accounts({"a@b.com": "not-a-mapping"}, "a@b.com")


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


def test_select_dto_and_product() -> None:
    offers = [
        {"offerSubType": "OTHER", "offerId": "A"},
        {
            "offerSubType": "DTO",
            "offerId": "DTO1",
            "products": [
                {"productId": "PDATA", "productFamily": "DATA"},
                {"productId": "PVOICE", "productFamily": "VOICE"},
            ],
        },
    ]
    dto = select_dto_offer(offers)
    assert dto is not None
    assert dto["offerId"] == "DTO1"
    assert select_transfer_product_id(dto, "VOICE") == "PVOICE"
    assert select_transfer_product_id(dto, "UNKNOWN") == "PDATA"


def test_assemble_transfer_payload_shape() -> None:
    offers = [
        {
            "offerSubType": "DTO",
            "offerId": "DTO1",
            "products": [{"productId": "PDATA", "productFamily": "DATA"}],
        }
    ]
    payload = assemble_transfer_payload(
        offers,
        product_family="DATA",
        source_msisdn="111",
        subscription_id="s",
        target_msisdn="222",
        user_offer_id="UO",
        balance_resource_id=9,
        unit="MB",
        amount=500.0,
    )
    assert payload is not None
    assert "tranferOrder" in payload
    offer = payload["tranferOrder"]["orderSubscription"]["offers"][0]
    assert offer["offerId"] == "DTO1"
    assert offer["offerProduct"]["productData"] == {"unit": "MB", "volume": 500.0}
    assert assemble_transfer_payload([], product_family="DATA", source_msisdn="1", subscription_id="s", target_msisdn="2", user_offer_id="u", balance_resource_id=1, unit="MB", amount=1.0) is None


def test_build_active_offers_vas_usage() -> None:
    raw = [
        {
            "offerId": "OFF1",
            "offerType": "VAS",
            "offerSubType": "LOCAL",
            "planStatus": "ACTIVE",
            "transferAllowed": False,
            "offerNameChi": "套餐",
            "offerDescChi": "描述",
            "offerPrice": 10,
            "endDate": "2025-01-01T00:00:00",
            "subscriptionProducts": [
                {
                    "productName": "Data Pack",
                    "productSpecType": "DATA",
                    "transferAllowed": False,
                    "minTransferQuota": 0,
                    "matrixxBalanceInfos": [
                        {
                            "unit": "MB",
                            "grantAmount": 1000,
                            "amount": 400,
                            "resourceId": "r1",
                        }
                    ],
                }
            ],
        }
    ]
    offers = build_active_offers(raw)
    assert len(offers) == 1
    assert offers[0]["offerId"] == "OFF1"
    assert offers[0]["usage"][0]["total"] == 1000
    assert offers[0]["usage"][0]["remain"] == 400
    assert offers[0]["endDate"] == "2025-01-01"


def test_build_profile_from_brand_responses() -> None:
    brand_data = {
        "email": "a@b.com",
        "subscriptions": [
            {
                "primaryMsisdn": "85212345678",
                "subscriptionId": "sub-1",
                "activationDate": "2024-01-01T00:00:00",
                "subsEndDate": "2025-01-01T00:00:00",
                "iccid": "icc",
                "status": "ACTIVE",
                "subscriptionOffers": [
                    {
                        "offerId": "OFF1",
                        "offerType": "VAS",
                        "offerSubType": "LOCAL",
                        "planStatus": "ACTIVE",
                        "transferAllowed": False,
                        "subscriptionProducts": [
                            {
                                "productName": "Data Pack",
                                "productSpecType": "DATA",
                                "transferAllowed": False,
                                "minTransferQuota": 0,
                                "matrixxBalanceInfos": [
                                    {
                                        "unit": "MB",
                                        "grantAmount": 1000,
                                        "amount": 400,
                                        "resourceId": "r1",
                                    }
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }
    result = build_profile_from_brand_responses(
        [("THREE", brand_data)],
        available_accounts=[
            {"identifier": "a@b.com", "active": True, "subBrand": "THREE"}
        ],
    )
    assert result["status"] == "success"
    assert result["data"]["email"] == "a@b.com"
    assert result["data"]["subscriptions"][0]["mobile"] == "85212345678"
    assert result["data"]["current"]["brand"] == "THREE"
