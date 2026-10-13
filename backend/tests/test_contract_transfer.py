from __future__ import annotations

import json
from typing import Any

import pytest

from app import main
from app.routes import transfer
from tests.contract_support import (
    FakeResponse,
    MonkeyPatch,
    authed_request,
    run_endpoint,
)


@pytest.fixture(autouse=True)
def _verified_resource(monkeypatch):
    # Only upstream payload contracts bypass the separately tested read checks.
    monkeypatch.setattr(transfer, "validate_transfer", lambda *args: "THREE")


def test_transfer_no_dto_offer_returns_400(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "make_3hk_request",
        lambda **kw: FakeResponse(200, {"offers": [{"offerSubType": "OTHER"}]}),
    )
    request = authed_request(
        "/api/sim/transfer",
        "POST",
        content_type="application/json",
        body=json.dumps({"account_id": "a@b.com", "subscriptionId": "s"}).encode(),
    )
    resp = run_endpoint("/api/sim/transfer", request)
    assert resp.status_code == 400
    assert json.loads(bytes(resp.body)) == {"status": "error", "message": "不支持转移"}


def test_transfer_success_payload_and_cache_invalidation(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: list[dict[str, Any]] = []
    invalidated: list[str] = []

    def fake_make(**kw):
        captured.append({"url": kw.get("url"), "json": kw.get("json_data")})
        if "getTransferOffers" in (kw.get("url") or ""):
            return FakeResponse(
                200,
                {
                    "offers": [
                        {
                            "offerSubType": "DTO",
                            "offerId": "DTO1",
                            "products": [
                                {"productId": "PDATA", "productFamily": "DATA"},
                                {"productId": "PVOICE", "productFamily": "VOICE"},
                            ],
                        }
                    ]
                },
            )
        return FakeResponse(200, {})

    monkeypatch.setattr(main, "make_3hk_request", fake_make)
    monkeypatch.setattr(main, "delete_cache", lambda k: invalidated.append(k))
    body = {
        "account_id": "a@b.com",
        "subscriptionId": "s",
        "sourceMsisdn": "11111111",
        "targetMsisdn": "22222222",
        "productFamily": "DATA",
        "balanceResourceId": "9",
        "unit": "MB",
        "amount": "500",
        "userOfferId": "UO",
    }
    resp = run_endpoint(
        "/api/sim/transfer",
        authed_request(
            "/api/sim/transfer",
            "POST",
            content_type="application/json",
            body=json.dumps(body).encode(),
        ),
    )
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body)) == {"status": "success"}
    assert invalidated == ["profile_sid-seeded_a@b.com"]
    payload = captured[-1]["json"]
    assert "tranferOrder" in payload
    order_sub = payload["tranferOrder"]["orderSubscription"]
    assert order_sub["msisdn"] == "11111111"
    assert order_sub["volumeUpMsisdn"] == "22222222"
    offer = order_sub["offers"][0]
    assert offer["offerId"] == "DTO1"
    assert offer["transferOfferId"] == "UO"
    assert offer["offerProduct"]["balanceResourceId"] == 9
    assert offer["offerProduct"]["productId"] == "PDATA"
    assert offer["offerProduct"]["productData"] == {"unit": "MB", "volume": 500.0}


def test_transfer_upstream_non_200_returns_400(monkeypatch: MonkeyPatch) -> None:
    def fake_make(**kw):
        if "getTransferOffers" in (kw.get("url") or ""):
            return FakeResponse(
                200,
                {
                    "offers": [
                        {
                            "offerSubType": "DTO",
                            "offerId": "D",
                            "products": [{"productId": "P", "productFamily": "DATA"}],
                        }
                    ]
                },
            )
        return FakeResponse(500)

    monkeypatch.setattr(main, "make_3hk_request", fake_make)
    body = {
        "account_id": "a@b.com",
        "subscriptionId": "s",
        "productFamily": "DATA",
        "balanceResourceId": 1,
        "amount": 1,
        "unit": "MB",
        "sourceMsisdn": "11111111",
        "targetMsisdn": "22222222",
        "userOfferId": "u",
    }
    resp = run_endpoint(
        "/api/sim/transfer",
        authed_request(
            "/api/sim/transfer",
            "POST",
            content_type="application/json",
            body=json.dumps(body).encode(),
        ),
    )
    assert resp.status_code == 400
    assert json.loads(bytes(resp.body)) == {
        "status": "error",
        "message": "资源转移请求失败，请稍后重试",
        "code": "upstream_error",
    }
