"""Unit tests for pure service helpers (no ASGI / monkeypatch seams)."""

from __future__ import annotations

import pytest

from app.services_profile import (
    build_active_offers,
    build_available_accounts,
    build_profile_from_brand_responses,
    build_subscription_entry,
    fuzzy_time_key,
    merge_brand_profile_data,
    safe_date_str,
)


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
