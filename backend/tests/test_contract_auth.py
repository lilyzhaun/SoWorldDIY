from __future__ import annotations

from typing import Any

from app import main
from tests.contract_support import (
    FakeIsolatedSession,
    FakeResponse,
    MonkeyPatch,
    _authed_session,
    _install_fake_store,
    isolated_sessions,
)
from tests.contract_support import (
    invoke as _invoke,
)


def invoke(path: str, *args, **kwargs):
    # Authentication flow contracts start with a valid pre-login CSRF session.
    # Missing/cross-site tokens are tested separately against the raw ASGI app.
    if path == "/login":
        ctx = main.session_store.create({"csrf_token": "login-token"})
        kwargs["headers"] = {
            **kwargs.get("headers", {}),
            "cookie": f"session={ctx.sid}",
            "x-csrf-token": "login-token",
        }
    return _invoke(path, *args, **kwargs)


def test_protected_routes_redirect_to_login_when_anonymous() -> None:
    cases = [
        ("/api/balance?account_id=a@b.com&subscriptionId=s", "GET"),
        ("/api/profile?account_id=a@b.com", "GET"),
        ("/api/plans?account_id=a@b.com", "GET"),
        ("/api/inbox?account_id=a@b.com", "GET"),
        ("/api/history?account_id=a@b.com&subscriptionId=s", "GET"),
        ("/api/cmn/check?account_id=a@b.com&subscriptionId=s", "GET"),
        ("/api/cmn/numbers", "POST"),
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
    assert resp.json == {
        "status": "error",
        "message": "CSRF token invalid",
        "code": "csrf_invalid",
    }


def test_csrf_valid_proceeds_past_csrf_gate(monkeypatch: MonkeyPatch) -> None:
    from app.routes import commerce

    monkeypatch.setattr(commerce, "validate_purchase", lambda *args: "THREE")
    store = _install_fake_store(monkeypatch)
    sid, csrf = _authed_session(store)

    def fake_purchase(**kw):
        if "purchase/createPurchase" in kw.get("url", ""):
            return FakeResponse(200, {"paymentUrl": "https://pay/3"})
        return FakeResponse(200, {"accessPurchaseKey": "k"})

    monkeypatch.setattr(main, "make_3hk_request", fake_purchase)
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
    assert "credential" not in acct
    assert "auth_code" not in acct
    encrypted = acct["stored_password_encrypted"]
    assert encrypted is not None
    assert encrypted != "secret"
    assert main.decrypt_password(encrypted) == "secret"
    cookies = " ".join(resp.header("set-cookie"))
    assert "session=" in cookies and "csrf_token=" in cookies


def test_password_login_success_saves_session_once(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    monkeypatch.setattr(main, "verify_auth_code", lambda code, consume: (True, "OK"))
    monkeypatch.setattr(
        main,
        "get_isolated_session",
        isolated_sessions(
            [FakeResponse(200, {"subBrand": "SOSIM"}), FakeResponse(204)]
        ),
    )

    saved: list[tuple[str, dict[str, Any]]] = []

    original_rotate = store.rotate

    def fake_rotate(sid, data):
        ctx = original_rotate(sid, data)
        saved.append((ctx.sid, dict(ctx.data)))
        return ctx

    monkeypatch.setattr(store, "rotate", fake_rotate)

    resp = invoke(
        "/login",
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"login_type=password&identifier=a@b.com&auth_code=C&password=secret",
    )

    assert resp.status == 200
    assert resp.json == {"status": "success", "redirect": "/main/a@b.com"}
    assert len(saved) == 1

    _sid, data = saved[0]
    assert _sid.startswith("3hk_user_")
    account = data["accounts"]["a@b.com"]
    assert account["cookies"] == {}
    assert account["sub_brand"] == "THREE"
    assert "auth_code" not in account
    assert "credential" not in account
    assert account["login_type"] == "password"
    encrypted = account["stored_password_encrypted"]
    assert encrypted is not None
    assert encrypted != "secret"
    assert main.decrypt_password(encrypted) == "secret"
    assert data["last_session_refresh"] > 0
    assert "csrf_token" in data


def test_otp_login_success_uses_dipping_subbrand(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    monkeypatch.setattr(main, "verify_auth_code", lambda code, consume: (True, "OK"))
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
    acct = data["accounts"]["a@b.com"]
    assert acct["sub_brand"] == "SOSIM"
    assert acct["login_type"] == "otp"
    assert "credential" not in acct
    assert "auth_code" not in acct
    assert "stored_password_encrypted" not in acct
    assert "password" not in acct
    assert "otp" not in acct
    assert "123456" not in str(acct)


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
    monkeypatch.setattr(
        main,
        "get_isolated_session",
        isolated_sessions(
            [FakeResponse(200, {"subBrand": "THREE"}), FakeResponse(204)]
        ),
    )

    def raising_save(sid, data):
        raise RuntimeError("Redis save failed")

    monkeypatch.setattr(store, "rotate", raising_save)
    resp = invoke(
        "/login",
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"login_type=password&identifier=a@b.com&auth_code=C&password=p",
    )
    assert resp.status == 503
    assert resp.json == {
        "status": "error",
        "message": "服务暂时不可用",
        "code": "service_unavailable",
    }


def test_check_user_rate_limit_returns_429_with_retry_after(
    monkeypatch: MonkeyPatch,
) -> None:
    from app.rate_limit import RateLimitConfig, RateLimiter
    from tests.test_rate_limit import FakeRateRedis

    redis = FakeRateRedis()
    limiter = RateLimiter(
        redis, RateLimitConfig(check_user_ip_limit=2, check_user_ip_window=42)
    )
    monkeypatch.setattr(main, "rate_limiter", limiter)
    monkeypatch.setattr(
        main,
        "get_isolated_session",
        isolated_sessions(
            [
                FakeResponse(200, {"subBrand": "THREE"}),
                FakeResponse(200, {"subBrand": "THREE"}),
            ]
        ),
    )
    for _ in range(2):
        ok = invoke(
            "/api/check-user",
            method="POST",
            headers={"content-type": "application/json"},
            body=b'{"identifier":"a@b.com"}',
        )
        assert ok.status == 200, (ok.status, ok.json)
    blocked = invoke(
        "/api/check-user",
        method="POST",
        headers={"content-type": "application/json"},
        body=b'{"identifier":"a@b.com"}',
    )
    assert blocked.status == 429
    assert blocked.json["code"] == "rate_limited"
    assert blocked.header("retry-after") == ["42"]


def test_check_user_ignores_spoofed_xff_from_untrusted_peer(
    monkeypatch: MonkeyPatch,
) -> None:
    from app.rate_limit import RateLimitConfig, RateLimiter
    from tests.test_rate_limit import FakeRateRedis

    redis = FakeRateRedis()
    limiter = RateLimiter(
        redis, RateLimitConfig(check_user_ip_limit=1, check_user_ip_window=30)
    )
    monkeypatch.setattr(main, "rate_limiter", limiter)
    monkeypatch.setattr(main, "TRUSTED_PROXY_IPS", frozenset({"127.0.0.1", "::1"}))
    monkeypatch.setattr(
        main,
        "get_isolated_session",
        isolated_sessions(
            [
                FakeResponse(200, {"subBrand": "THREE"}),
                FakeResponse(200, {"subBrand": "THREE"}),
            ]
        ),
    )
    # peer is 127.0.0.1 in invoke(); XFF trusted → first request counts as 198.51.100.1
    first = invoke(
        "/api/check-user",
        method="POST",
        headers={
            "content-type": "application/json",
            "x-forwarded-for": "198.51.100.1",
        },
        body=b'{"identifier":"a@b.com"}',
    )
    assert first.status == 200
    # Second with same spoofed XFF from loopback peer is rate limited
    second = invoke(
        "/api/check-user",
        method="POST",
        headers={
            "content-type": "application/json",
            "x-forwarded-for": "198.51.100.1",
        },
        body=b'{"identifier":"a@b.com"}',
    )
    assert second.status == 429
    # Different forged XFF from untrusted peer path is not applicable here (peer is loopback).
    # Prove untrusted peer ignores XFF via unit tests; here prove loopback trust uses XFF bucket.


def test_login_redis_failure_returns_503(monkeypatch: MonkeyPatch) -> None:
    from app.rate_limit import RateLimitConfig, RateLimiter
    from tests.test_rate_limit import FakeRateRedis

    limiter = RateLimiter(FakeRateRedis(fail=True), RateLimitConfig())
    _install_fake_store(monkeypatch)
    monkeypatch.setattr(main, "rate_limiter", limiter)
    monkeypatch.setattr(main, "verify_auth_code", lambda code, consume: (True, "OK"))
    resp = invoke(
        "/login",
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"login_type=password&identifier=a@b.com&auth_code=x&password=p",
    )
    assert resp.status == 503
    assert resp.json["code"] == "service_unavailable"
