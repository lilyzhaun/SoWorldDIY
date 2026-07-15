from __future__ import annotations

import json

from app import main
from tests.contract_support import (
    FakeResponse,
    MonkeyPatch,
    authed_request,
    run_endpoint,
)


def test_cmn_check_no_offers_returns_400(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        main, "make_3hk_request", lambda **kw: FakeResponse(200, {"offers": []})
    )
    request = authed_request("/api/cmn/check", "GET")
    request.scope["query_string"] = b"account_id=a@b.com&subscriptionId=s"
    resp = run_endpoint("/api/cmn/check", request)
    assert resp.status_code == 400
    assert json.loads(bytes(resp.body)) == {"status": "error", "message": "无资格"}


def test_cmn_check_returns_first_offer(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "make_3hk_request",
        lambda **kw: FakeResponse(
            200,
            {
                "offers": [
                    {
                        "offerId": "C1",
                        "offerSubType": "CMN",
                        "offerPrice": 88,
                        "offerNameChi": "換號",
                    }
                ]
            },
        ),
    )
    request = authed_request("/api/cmn/check", "GET")
    request.scope["query_string"] = b"account_id=a@b.com&subscriptionId=s"
    resp = run_endpoint("/api/cmn/check", request)
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body)) == {
        "status": "success",
        "data": {"offerId": "C1", "offerSubType": "CMN", "price": 88, "name": "換號"},
    }


def test_cmn_numbers_post_returns_sorted_unique_from_form(
    monkeypatch: MonkeyPatch,
) -> None:
    captured: list[str] = []
    monkeypatch.setattr(
        main,
        "make_3hk_request",
        lambda **kw: (
            captured.append(kw.get("method", "")),
            FakeResponse(200, {"lineList": ["333", "111", "111", "222"]}),
        )[1],
    )
    request = authed_request(
        "/api/cmn/numbers",
        "POST",
        content_type="application/x-www-form-urlencoded",
        body=b"account_id=a%40b.com&subscriptionId=s",
    )
    resp = run_endpoint("/api/cmn/numbers", request)
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body)) == {
        "status": "success",
        "numbers": ["111", "222", "333"],
    }
    assert captured == ["POST"]


def test_cmn_numbers_fetch_fail_returns_400(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(main, "make_3hk_request", lambda **kw: None)
    request = authed_request(
        "/api/cmn/numbers",
        "POST",
        content_type="application/x-www-form-urlencoded",
        body=b"account_id=a%40b.com&subscriptionId=s",
    )
    resp = run_endpoint("/api/cmn/numbers", request)
    assert resp.status_code == 400
    assert json.loads(bytes(resp.body)) == {
        "status": "error",
        "message": "Fetch failed",
    }


def test_cmn_numbers_post_returns_sorted_unique(monkeypatch: MonkeyPatch) -> None:
    captured: list[str] = []
    monkeypatch.setattr(
        main,
        "make_3hk_request",
        lambda **kw: (
            captured.append(kw.get("method", "")),
            FakeResponse(200, {"lineList": ["222", "111", "111", "333"]}),
        )[1],
    )
    request = authed_request(
        "/api/cmn/numbers",
        "POST",
        content_type="application/x-www-form-urlencoded",
        body=b"account_id=a%40b.com&subscriptionId=s",
    )
    resp = run_endpoint("/api/cmn/numbers", request)
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body)) == {
        "status": "success",
        "numbers": ["111", "222", "333"],
    }
    assert captured == ["POST"]


def test_cmn_numbers_post_without_csrf_returns_403(monkeypatch: MonkeyPatch) -> None:
    request = authed_request(
        "/api/cmn/numbers",
        "POST",
        csrf=None,
        content_type="application/x-www-form-urlencoded",
        body=b"account_id=a@b.com&subscriptionId=s",
    )
    resp = run_endpoint("/api/cmn/numbers", request)
    assert resp.status_code == 403
    assert json.loads(bytes(resp.body)) == {
        "status": "error",
        "message": "CSRF token invalid",
    }
