"""Contract tests: /login flow."""

from __future__ import annotations

from pytest import MonkeyPatch

from app import main
from tests.contract_helpers import (
    FakeIsolatedSession,
    FakeResponse,
    _install_fake_store,
    invoke,
    isolated_sessions,
)


def test_login_invalid_auth_code_returns_400(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    monkeypatch.setattr(main, "verify_auth_code", lambda code, consume: (False, "请输入鉴权码"))
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
    monkeypatch.setattr(main, "get_isolated_session", isolated_sessions([FakeResponse(500)]))
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

    monkeypatch.setattr(main, "get_isolated_session", lambda: BoomSession(FakeResponse(204)))
    resp = invoke(
        "/login",
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"login_type=password&identifier=a@b.com&auth_code=C&password=p",
    )
    assert resp.status == 500
    assert resp.json["status"] == "error"
    assert "账号检查失败" in resp.json["message"]


def test_password_login_success_sets_session_and_redirect(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    monkeypatch.setattr(main, "verify_auth_code", lambda code, consume: (True, "OK"))
    monkeypatch.setattr(main, "notify", lambda msg: None)
    # existingCustDipping returns SOSIM, but password login forces THREE.
    monkeypatch.setattr(
        main,
        "get_isolated_session",
        isolated_sessions([FakeResponse(200, {"subBrand": "SOSIM"}), FakeResponse(204)]),
    )
    resp = invoke(
        "/login",
        method="POST",
        headers={"content-type": "application/x-www-form-urlencoded"},
        body=b"login_type=password&identifier=a@b.com&auth_code=C&password=secret",
    )
    assert resp.status == 200
    assert resp.json == {"status": "success", "redirect": "/main/a@b.com"}
    # session persisted with THREE brand regardless of dipping result
    assert len(store.sessions) == 1
    _, data = next(iter(store.sessions.items()))
    acct = data["accounts"]["a@b.com"]
    assert acct["sub_brand"] == "THREE"
    assert acct["login_type"] == "password"
    assert acct["stored_password_encrypted"] is not None
    assert acct["credential"] == "secret"
    # cookies set on response
    cookies = " ".join(resp.header("set-cookie"))
    assert "session=" in cookies and "csrf_token=" in cookies


def test_otp_login_success_uses_dipping_subbrand(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    monkeypatch.setattr(main, "verify_auth_code", lambda code, consume: (True, "OK"))
    monkeypatch.setattr(main, "notify", lambda msg: None)
    monkeypatch.setattr(
        main,
        "get_isolated_session",
        isolated_sessions([FakeResponse(200, {"subBrand": "SOSIM"}), FakeResponse(204)]),
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
        isolated_sessions([FakeResponse(200, {"subBrand": "THREE"}), FakeResponse(400)]),
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
        isolated_sessions([FakeResponse(200, {"subBrand": "THREE"}), FakeResponse(204)]),
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

