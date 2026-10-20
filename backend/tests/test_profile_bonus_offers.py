"""Regression coverage for promotional quotas and repeated offer instances."""

from __future__ import annotations

import pytest

from app.services_profile import build_active_offers


def _bonus(resource_id: str = "bonus-1") -> dict[str, object]:
    return {
        "offerId": "BONUS300",
        "matrixxResourceId": resource_id,
        "offerType": "PROMOTION",
        "offerSubType": "BONUS",
        "planStatus": "ACTIVE",
        "offerNameChi": "增值獎賞 (300本地通話分鐘)",
        "offerPrice": 0,
        "endDate": "2027-10-21T00:00:00+08:00",
        "transferAllowed": False,
        "subscriptionProducts": [
            {
                "productName": "Local Voice 300 Minutes",
                "productSpecType": "VOICE",
                "transferAllowed": False,
                "matrixxBalanceInfos": [
                    {
                        "unit": "Minutes",
                        "grantAmount": 300,
                        "amount": 300,
                        "balanceResourceId": f"balance-{resource_id}",
                    }
                ],
            }
        ],
    }


@pytest.mark.parametrize("status", ["ACTIVE", "PREACTIVE"])
def test_bonus_voice_quota_is_visible(status: str) -> None:
    raw = _bonus()
    raw["planStatus"] = status

    offers = build_active_offers([raw])

    assert len(offers) == 1
    offer = offers[0]
    assert offer["name"] == "增值獎賞 (300本地通話分鐘)"
    assert offer["price"] == 0
    assert offer["endDate"] == "2027-10-21"
    assert offer["planStatus"] == status
    usage = offer["usage"][0]
    assert usage["total"] == usage["remain"] == 300
    assert usage["unit"] == "Minutes"
    assert usage["percent"] == 100
    assert usage["productFamily"] == "VOICE"
    assert usage["canTransfer"] is False


@pytest.mark.parametrize("status", ["EXPIRED", "CANCELLED", "INACTIVE"])
def test_inactive_bonus_is_hidden(status: str) -> None:
    raw = _bonus()
    raw["planStatus"] = status
    assert build_active_offers([raw]) == []


@pytest.mark.parametrize(
    ("offer_type", "sub_type"),
    [("PROMOTION", "LOCAL"), ("BASE", "LOCAL"), ("OTHER", "BONUS")],
)
def test_bonus_support_does_not_include_unrelated_offer_types(
    offer_type: str, sub_type: str
) -> None:
    raw = _bonus()
    raw.update(offerType=offer_type, offerSubType=sub_type)
    assert build_active_offers([raw]) == []


def test_bonus_without_non_monetary_usage_is_hidden() -> None:
    raw = _bonus()
    raw["subscriptionProducts"] = []
    assert build_active_offers([raw]) == []
    raw["subscriptionProducts"] = [
        {"matrixxBalanceInfos": [{"unit": "HKD", "grantAmount": 10, "amount": 10}]}
    ]
    assert build_active_offers([raw]) == []


@pytest.mark.parametrize("offer_type", ["PROMOTION", "VAS"])
def test_repeated_offers_keep_distinct_stable_instance_ids(offer_type: str) -> None:
    raw = [_bonus("38"), _bonus("33")]
    for offer in raw:
        offer["offerType"] = offer_type

    offers = build_active_offers(raw)

    assert len(offers) == 2
    assert offers[0]["instanceId"] != offers[1]["instanceId"]
    assert [offer["offerId"] for offer in offers] == ["BONUS300", "BONUS300"]
    assert sum(offer["usage"][0]["remain"] for offer in offers) == 600
    assert all(offer["usage"][0]["userOfferId"] == "BONUS300" for offer in offers)
    assert [offer["instanceId"] for offer in build_active_offers(raw[::-1])] == [
        offer["instanceId"] for offer in offers[::-1]
    ]


def test_repeated_offers_without_resource_ids_still_have_distinct_instances() -> None:
    raw = _bonus()
    del raw["matrixxResourceId"]
    offers = build_active_offers([raw, raw])
    assert len(offers) == 2
    assert offers[0]["instanceId"] != offers[1]["instanceId"]


def test_dto_voice_and_data_aggregation_keeps_separate_instances() -> None:
    raw = _bonus()
    raw.update(offerType="OTHER", offerSubType="DTO")
    raw["subscriptionProducts"] = [
        {
            "productSpecType": family,
            "matrixxBalanceInfos": [{"unit": unit, "grantAmount": 100, "amount": 50}],
        }
        for family, unit in [("VOICE", "Minutes"), ("DATA", "megabytes")]
    ]

    offers = build_active_offers([raw])

    assert [offer["offerId"] for offer in offers] == ["DTO_VOICE_AGG", "DTO_DATA_AGG"]
    assert [offer["instanceId"] for offer in offers] == [
        "DTO_VOICE_AGG",
        "DTO_DATA_AGG",
    ]
    assert all(offer["usage"][0]["userOfferId"] == "BONUS300" for offer in offers)
