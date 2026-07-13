from __future__ import annotations

import json
from typing import Any

from app import main
from tests.contract_support import (
    CSRF_HEADER_NAME,
    FakeResponse,
    MonkeyPatch,
    Request,
    _install_fake_store,
    authed_request,
    run_endpoint,
)


def _purchase_request(body: dict[str, Any], csrf: str | None = "tok") -> Request:
    return authed_request(
        "/api/purchase",
        "POST",
        headers={CSRF_HEADER_NAME: csrf} if csrf else {},
        content_type="application/json",
        body=json.dumps(body).encode(),
    )


def test_purchase_invalid_account_returns_401(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    request = authed_request(
        "/api/purchase",
        "POST",
        accounts={"other@x.com": {"cookies": {}}},
        content_type="application/json",
        body=json.dumps({"account_id": "missing@x.com"}).encode(),
    )
    resp = run_endpoint("/api/purchase", request)
    assert resp.status_code == 401
    assert json.loads(bytes(resp.body)) == {"status": "error", "message": "Auth failed"}


def test_purchase_access_key_none_returns_400(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(main, "make_3hk_request", lambda **kw: None)
    resp = run_endpoint(
        "/api/purchase",
        _purchase_request(
            {"account_id": "a@b.com", "subscriptionId": "s", "items": [], "price": 0}
        ),
    )
    assert resp.status_code == 400
    assert json.loads(bytes(resp.body)) == {
        "status": "error",
        "message": "Request failed",
    }


def test_purchase_normal_flow_payload_and_success(monkeypatch: MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_make(**kw):
        captured.append(
            {
                "url": kw.get("url"),
                "method": kw.get("method"),
                "json": kw.get("json_data"),
            }
        )
        if "purchase/createPurchase" in (kw.get("url") or ""):
            return FakeResponse(200, {"paymentUrl": "https://pay/x"})
        return FakeResponse(200, {"accessPurchaseKey": "KEY"})

    monkeypatch.setattr(main, "make_3hk_request", fake_make)
    monkeypatch.setattr(main, "handle_purchase_event", lambda *a, **k: None)
    invalidated: list[str] = []
    monkeypatch.setattr(main, "delete_cache", lambda k: invalidated.append(k))
    resp = run_endpoint(
        "/api/purchase",
        _purchase_request(
            {
                "account_id": "a@b.com",
                "subscriptionId": "s",
                "items": [{"offerId": "OFF", "quantity": 2}],
                "price": 100,
                "txnAmount": 30,
            }
        ),
    )
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body)) == {
        "status": "success",
        "paymentUrl": "https://pay/x",
    }
    assert invalidated == ["profile_a@b.com"]
    payload = captured[-1]["json"]
    assert payload["purchaseType"] == "SOSIM_VAS"
    assert payload["fUrl"] == "https://simworld.net/SIMworld/main/tc"
    assert payload["accessPurchaseKey"] == "KEY"
    order = payload["order"]
    assert order["channel"] == "ONLINE"
    assert order["autoPayFlag"] is False
    assert order["pmt"]["amnt"] == 70.0
    sub = order["orderSubscriptions"][0]
    assert sub["subscriptionId"] == "s"
    assert sub["offers"] == [{"offerId": "OFF", "quantity": 2, "autoRenewFlag": False}]
    assert sub["walletPayment"] == {"txnAmount": 30.0}


def test_purchase_new_line_flow_payload(monkeypatch: MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_make(**kw):
        captured.append({"url": kw.get("url"), "json": kw.get("json_data")})
        if "purchase/createPurchase" in (kw.get("url") or ""):
            return FakeResponse(200, {"paymentUrl": "https://pay/new"})
        return FakeResponse(200, {"accessPurchaseKey": "KEY"})

    monkeypatch.setattr(main, "make_3hk_request", fake_make)
    monkeypatch.setattr(main, "handle_purchase_event", lambda *a, **k: None)
    resp = run_endpoint(
        "/api/purchase",
        _purchase_request(
            {
                "account_id": "a@b.com",
                "subscriptionId": "s",
                "new_line": True,
                "items": [{"offerId": "VAS1", "quantity": 1}],
                "price": 0,
            }
        ),
    )
    assert resp.status_code == 200
    payload = captured[-1]["json"]
    assert payload["purchaseType"] == "PREPAID_DIY"
    assert payload["order"]["channel"] == "GLOBAL_ESIM"
    offers = payload["order"]["orderSubscription"]["offers"]
    assert offers[0] == {
        "offerId": "H3OF00000000001",
        "quantity": 1,
        "autoRenewFlag": False,
    }
    assert offers[1] == {"offerId": "VAS1", "quantity": 1, "autoRenewFlag": False}
    assert payload["order"]["orderSubscription"]["simType"] == "ESIM"


def test_purchase_upstream_no_payment_url_returns_400(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "make_3hk_request",
        lambda **kw: (
            FakeResponse(200, {"accessPurchaseKey": "k"})
            if "accessPurchaseKey" in (kw.get("url") or "")
            else FakeResponse(200, {"nope": 1})
        ),
    )
    resp = run_endpoint(
        "/api/purchase",
        _purchase_request(
            {"account_id": "a@b.com", "subscriptionId": "s", "items": [], "price": 0}
        ),
    )
    assert resp.status_code == 400
    assert json.loads(bytes(resp.body)) == {
        "status": "error",
        "message": "购买请求失败，请稍后重试",
    }
