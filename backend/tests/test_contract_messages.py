from __future__ import annotations

import json

from app import main
from tests.contract_support import (
    FakeResponse,
    MonkeyPatch,
    authed_request,
    run_endpoint,
)


def test_inbox_dedups_and_sorts_desc(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "make_3hk_request",
        lambda **kw: FakeResponse(
            200,
            {
                "inbox_msgs": [
                    {"msg_id": 1, "post_dt": "2024-01-01"},
                    {"msg_id": 2, "post_dt": "2024-03-01"},
                    {"msg_id": 1, "post_dt": "2024-01-01"},
                    {"msg_id": 3, "post_dt": "2024-02-01"},
                ]
            },
        ),
    )
    request = authed_request("/api/inbox", "GET")
    request.scope["query_string"] = b"account_id=a@b.com"
    resp = run_endpoint("/api/inbox", request)
    assert resp.status_code == 200
    body = json.loads(bytes(resp.body))
    ids = [m["msg_id"] for m in body["messages"]]
    assert ids == [2, 3, 1]


def test_history_upstream_non_200_returns_400_bare_error(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "make_3hk_request", lambda **kw: FakeResponse(500))
    request = authed_request("/api/history", "GET")
    request.scope["query_string"] = b"account_id=a@b.com&subscriptionId=s"
    resp = run_endpoint("/api/history", request)
    assert resp.status_code == 400
    assert json.loads(bytes(resp.body)) == {"status": "error"}


def test_history_success_wraps_upstream_json(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        main, "make_3hk_request", lambda **kw: FakeResponse(200, {"txns": [1, 2]})
    )
    request = authed_request("/api/history", "GET")
    request.scope["query_string"] = b"account_id=a@b.com&subscriptionId=s"
    resp = run_endpoint("/api/history", request)
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body)) == {
        "status": "success",
        "data": {"txns": [1, 2]},
    }
