"""Unit tests for pure service helpers (no ASGI / monkeypatch seams)."""

from __future__ import annotations

import pytest

from app.services_transfer import (
    assemble_transfer_payload,
    select_dto_offer,
    select_transfer_product_id,
)


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
    assert (
        assemble_transfer_payload(
            [],
            product_family="DATA",
            source_msisdn="1",
            subscription_id="s",
            target_msisdn="2",
            user_offer_id="u",
            balance_resource_id=1,
            unit="MB",
            amount=1.0,
        )
        is None
    )
