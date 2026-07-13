"""Contract tests: protected routes, pages, session cookies, CSRF."""

from __future__ import annotations

from pytest import MonkeyPatch

from app import main
from tests.contract_helpers import (
    FakeResponse,
    _authed_session,
    _install_fake_store,
    invoke,
)


def test_protected_routes_redirect_to_login_when_anonymous() -> None:
    # (path, http_method); POST-only routes must be hit with POST to reach the
    # handler (otherwise FastAPI returns 405 before auth runs).
    cases = [
        ("/api/balance?account_id=a@b.com&subscriptionId=s", "GET"),
        ("/api/profile?account_id=a@b.com", "GET"),
        ("/api/plans?account_id=a@b.com", "GET"),
        ("/api/inbox?account_id=a@b.com", "GET"),
        ("/api/history?account_id=a@b.com&subscriptionId=s", "GET"),
        ("/api/cmn/check?account_id=a@b.com&subscriptionId=s", "GET"),
        ("/api/cmn/numbers?account_id=a@b.com&subscriptionId=s", "GET"),
        ("/api/sim/transfer", "POST"),
        ("/api/purchase", "POST"),
        ("/api/cmn/purchase", "POST"),
        ("/main", "GET"),
        ("/main/a@b.com", "GET"),
    ]
    for path, method in cases:
        resp = invoke(path, method=method)
        assert resp.status == 302, f"{path} ({method}): expected 302, got {resp.status}"
        assert resp.header("location") == ["/"], f"{path}: location {resp.header('location')}"


def test_index_redirects_to_first_account_when_logged_in(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    sid, _ = _authed_session(
        store, accounts={"first@x.com": {"sub_brand": "THREE"}, "second@x.com": {"sub_brand": "SOSIM"}}
    )
    resp = invoke("/", headers={"cookie": f"session={sid}"})
    assert resp.status == 302
    assert resp.header("location") == ["/main/first@x.com"]


def test_index_serves_login_html_for_add_query() -> None:
    resp = invoke("/?add=1")
    assert resp.status == 200
    assert resp.header("content-type") and "text/html" in resp.header("content-type")[0]


def test_main_redirects_to_first_account(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    sid, _ = _authed_session(store, accounts={"a@b.com": {"sub_brand": "THREE"}})
    resp = invoke("/main", headers={"cookie": f"session={sid}"})
    assert resp.status == 302
    assert resp.header("location") == ["/main/a@b.com"]


def test_main_unknown_account_redirects_to_login(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    sid, _ = _authed_session(store, accounts={"a@b.com": {"sub_brand": "THREE"}})
    resp = invoke("/main/unknown@x.com", headers={"cookie": f"session={sid}"})
    assert resp.status == 302
    assert resp.header("location") == ["/"]


# =========================================================================
# Session / CSRF middleware cookies (ASGI driver)
# =========================================================================


def test_anonymous_request_sets_no_session_or_csrf_cookie() -> None:
    resp = invoke("/_health")
    set_cookie = resp.header("set-cookie")
    assert not any(c.startswith("session=") for c in set_cookie)
    assert not any(c.startswith("csrf_token=") for c in set_cookie)


def test_stale_session_cookie_is_deleted(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    # cookie present but not in the store -> middleware marks for deletion.
    resp = invoke("/api/balance?account_id=a@b.com", headers={"cookie": "session=ghost"})
    set_cookie = " ".join(resp.header("set-cookie"))
    assert "session=" in set_cookie and "Max-Age=0" in set_cookie
    assert "csrf_token=" in set_cookie and "Max-Age=0" in set_cookie


def test_logged_in_session_sets_session_and_csrf_cookies(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    sid, csrf = _authed_session(store)
    monkeypatch.setattr(main, "make_3hk_request", lambda **kw: FakeResponse(200, [{"amount": 0}]))
    resp = invoke("/api/balance?account_id=a@b.com&subscriptionId=s", headers={"cookie": f"session={sid}"})
    cookies = resp.header("set-cookie")
    session_cookie = [c for c in cookies if c.startswith("session=")][0]
    csrf_cookie = [c for c in cookies if c.startswith("csrf_token=")][0]
    assert f"session={sid}" in session_cookie
    assert f"csrf_token={csrf}" in csrf_cookie
    # session cookie: httponly, samesite=lax, path=/
    assert "HttpOnly" in session_cookie
    assert "SameSite=lax" in session_cookie
    assert "Path=/" in session_cookie
    # csrf cookie: NOT httponly
    assert "HttpOnly" not in csrf_cookie
    assert "SameSite=lax" in csrf_cookie


def test_csrf_missing_on_post_returns_403(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    sid, _ = _authed_session(store)
    resp = invoke(
        "/api/purchase",
        method="POST",
        headers={"cookie": f"session={sid}", "content-type": "application/json"},
        body=b'{"account_id":"a@b.com","subscriptionId":"s","items":[]}',
    )
    assert resp.status == 403
    assert resp.json == {"status": "error", "message": "CSRF token invalid"}


def test_csrf_valid_proceeds_past_csrf_gate(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    sid, csrf = _authed_session(store)
    monkeypatch.setattr(
        main,
        "make_3hk_request",
        lambda **kw: FakeResponse(200, {"accessPurchaseKey": "k"}),
    )

    def fake_purchase(**kw):
        if "purchase/createPurchase" in kw.get("url", ""):
            return FakeResponse(200, {"paymentUrl": "https://pay/3"})
        return FakeResponse(200, {"accessPurchaseKey": "k"})

    monkeypatch.setattr(main, "make_3hk_request", fake_purchase)
    monkeypatch.setattr(main, "handle_purchase_event", lambda *a, **k: None)

    resp = invoke(
        "/api/purchase",
        method="POST",
        headers={"cookie": f"session={sid}", "x-csrf-token": csrf, "content-type": "application/json"},
        body=b'{"account_id":"a@b.com","subscriptionId":"s","items":[{"offerId":"O","quantity":1}],"price":0}',
    )
    assert resp.status == 200
    assert resp.json == {"status": "success", "paymentUrl": "https://pay/3"}

