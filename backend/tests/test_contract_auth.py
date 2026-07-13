from __future__ import annotations

from app import main
from tests.contract_support import (
    FakeIsolatedSession,
    FakeResponse,
    MonkeyPatch,
    _authed_session,
    _install_fake_store,
    invoke,
    isolated_sessions,
)


def test_protected_routes_redirect_to_login_when_anonymous() -> None:
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
        assert resp.header("location") == ["/"], (
            f"{path}: location {resp.header('location')}"
        )


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

    def fake_purchase(**kw):
        if "purchase/createPurchase" in kw.get("url", ""):
            return FakeResponse(200, {"paymentUrl": "https://pay/3"})
        return FakeResponse(200, {"accessPurchaseKey": "k"})

    monkeypatch.setattr(main, "make_3hk_request", fake_purchase)
    monkeypatch.setattr(main, "handle_purchase_event", lambda *a, **k: None)
    resp = invoke(
        "/api/purchase",
        method="POST",
        headers={
            "cookie": f"session={sid}",
            "x-csrf-token": csrf,
            "content-type": "application/json",
        },
        body=b'{"account_id":"a@b.com","subscriptionId":"s","items":[{"offerId":"O","quantity":1}],"price":0}',
    )
    assert resp.status == 200
    assert resp.json == {"status": "success", "paymentUrl": "https://pay/3"}


def test_login_invalid_auth_code_returns_400(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    monkeypatch.setattr(
        main, "verify_auth_code", lambda code, consume: (False, "请输入鉴权码")
    )
    resp = invoke(
        "/login",
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"login_type=password&identifier=a@b.com&auth_code=&password=p",
    )
    assert resp.status == 400
    assert resp.json == {"status": "error", "message": "请输入鉴权码"}


def test_login_account_check_failure_returns_400(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    monkeypatch.setattr(main, "verify_auth_code", lambda code, consume: (True, "OK"))
    monkeypatch.setattr(
        main, "get_isolated_session", isolated_sessions([FakeResponse(500)])
    )
    resp = invoke(
        "/login",
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"login_type=password&identifier=a@b.com&auth_code=C&password=p",
    )
    assert resp.status == 400
    assert resp.json == {"status": "error", "message": "账号无效或网络错误"}


def test_login_account_check_exception_returns_500(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    monkeypatch.setattr(main, "verify_auth_code", lambda code, consume: (True, "OK"))

    class BoomSession(FakeIsolatedSession):
        def post(self, *a, **k):
            raise ConnectionError("net-down")

    monkeypatch.setattr(
        main, "get_isolated_session", lambda: BoomSession(FakeResponse(204))
    )
    resp = invoke(
        "/login",
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"login_type=password&identifier=a@b.com&auth_code=C&password=p",
    )
    assert resp.status == 500
    assert resp.json["status"] == "error"
    assert "账号检查失败" in resp.json["message"]


def test_password_login_success_sets_session_and_redirect(
    monkeypatch: MonkeyPatch,
) -> None:
    store = _install_fake_store(monkeypatch)
    monkeypatch.setattr(main, "verify_auth_code", lambda code, consume: (True, "OK"))
    monkeypatch.setattr(main, "notify", lambda msg: None)
    monkeypatch.setattr(
        main,
        "get_isolated_session",
        isolated_sessions(
            [FakeResponse(200, {"subBrand": "SOSIM"}), FakeResponse(204)]
        ),
    )
    resp = invoke(
        "/login",
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"login_type=password&identifier=a@b.com&auth_code=C&password=secret",
    )
    assert resp.status == 200
    assert resp.json == {"status": "success", "redirect": "/main/a@b.com"}
    assert len(store.sessions) == 1
    _, data = next(iter(store.sessions.items()))
    acct = data["accounts"]["a@b.com"]
    assert acct["sub_brand"] == "THREE"
    assert acct["login_type"] == "password"
    assert acct["stored_password_encrypted"] is not None
    assert acct["credential"] == "secret"
    cookies = " ".join(resp.header("set-cookie"))
    assert "session=" in cookies and "csrf_token=" in cookies


def test_otp_login_success_uses_dipping_subbrand(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    monkeypatch.setattr(main, "verify_auth_code", lambda code, consume: (True, "OK"))
    monkeypatch.setattr(main, "notify", lambda msg: None)
    monkeypatch.setattr(
        main,
        "get_isolated_session",
        isolated_sessions(
            [FakeResponse(200, {"subBrand": "SOSIM"}), FakeResponse(204)]
        ),
    )
    resp = invoke(
        "/login",
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"login_type=otp&identifier=a@b.com&auth_code=C&otp=123456",
    )
    assert resp.status == 200
    assert resp.json == {"status": "success", "redirect": "/main/a@b.com"}
    _, data = next(iter(store.sessions.items()))
    assert data["accounts"]["a@b.com"]["sub_brand"] == "SOSIM"
    assert data["accounts"]["a@b.com"]["credential"] == "OTP: 123456"


def test_login_upstream_non_204_returns_401(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    monkeypatch.setattr(main, "verify_auth_code", lambda code, consume: (True, "OK"))
    monkeypatch.setattr(
        main,
        "get_isolated_session",
        isolated_sessions(
            [FakeResponse(200, {"subBrand": "THREE"}), FakeResponse(400)]
        ),
    )
    resp = invoke(
        "/login",
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"login_type=password&identifier=a@b.com&auth_code=C&password=p",
    )
    assert resp.status == 401
    assert resp.json == {"status": "error", "message": "登录失败，请检查密码或OTP"}


def test_login_session_save_failure_returns_503(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    monkeypatch.setattr(main, "verify_auth_code", lambda code, consume: (True, "OK"))
    monkeypatch.setattr(main, "notify", lambda msg: None)
    monkeypatch.setattr(
        main,
        "get_isolated_session",
        isolated_sessions(
            [FakeResponse(200, {"subBrand": "THREE"}), FakeResponse(204)]
        ),
    )

    def raising_save(sid, data):
        raise RuntimeError("Redis save failed")

    monkeypatch.setattr(store, "save", raising_save)
    resp = invoke(
        "/login",
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"login_type=password&identifier=a@b.com&auth_code=C&password=p",
    )
    assert resp.status == 503
    assert resp.json == {"status": "error", "message": "Redis save failed"}
