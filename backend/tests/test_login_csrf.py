import pytest
from pytest import MonkeyPatch

from app import main
from tests.contract_support import (
    FakeResponse,
    _install_fake_store,
    invoke,
    isolated_sessions,
)


def prepare_login(monkeypatch):
    store = _install_fake_store(monkeypatch)
    ctx = store.create(
        {"csrf_token": "token", "accounts": {"existing": {"cookies": {}}}}
    )
    monkeypatch.setattr(main, "verify_auth_code", lambda code, consume: (True, "OK"))
    monkeypatch.setattr(
        main,
        "get_isolated_session",
        isolated_sessions(
            [FakeResponse(200, {"subBrand": "THREE"}), FakeResponse(204)]
        ),
    )
    return store, ctx


@pytest.mark.parametrize(
    "headers",
    [
        {},
        {"x-csrf-token": "token"},
        {"cookie": "session=missing", "x-csrf-token": "token"},
    ],
)
def test_login_requires_prelogin_session(monkeypatch: MonkeyPatch, headers):
    _install_fake_store(monkeypatch)
    response = invoke(
        "/login", method="POST", headers=headers, body=b"login_type=password"
    )
    assert response.status == 403


@pytest.mark.parametrize(
    "extra",
    [
        {"x-csrf-token": "wrong"},
        {"origin": "https://untrusted.example"},
        {"origin": "null"},
        {"sec-fetch-site": "cross-site"},
    ],
)
def test_login_rejects_cross_site_and_wrong_csrf(monkeypatch: MonkeyPatch, extra):
    store, ctx = prepare_login(monkeypatch)
    headers = {
        "cookie": f"session={ctx.sid}",
        "x-csrf-token": "token",
        "content-type": "application/x-www-form-urlencoded",
        **extra,
    }
    response = invoke(
        "/login",
        method="POST",
        headers=headers,
        body=b"login_type=password&identifier=new&password=p&auth_code=C",
    )
    assert response.status == 403
    assert list(store.load(ctx.sid)["accounts"]) == ["existing"]


def test_successful_login_rotates_sid_and_csrf(monkeypatch: MonkeyPatch):
    store, ctx = prepare_login(monkeypatch)
    response = invoke(
        "/login",
        method="POST",
        headers={
            "cookie": f"session={ctx.sid}",
            "x-csrf-token": "token",
            "origin": "http://127.0.0.1:8000",
            "content-type": "application/x-www-form-urlencoded",
        },
        body=b"login_type=password&identifier=new&password=p&auth_code=C",
    )
    assert response.status == 200
    assert store.load(ctx.sid) is None
    assert len(store.sessions) == 1
    data = next(iter(store.sessions.values()))
    assert set(data["accounts"]) == {"existing", "new"}
    assert data["csrf_token"] != "token"


def test_revoked_session_cannot_be_inherited_during_login(monkeypatch: MonkeyPatch):
    store, ctx = prepare_login(monkeypatch)
    original = store.rotate

    def revoke_then_rotate(sid, data):
        store.delete(sid)
        return original(sid, data)

    monkeypatch.setattr(store, "rotate", revoke_then_rotate)
    response = invoke(
        "/login",
        method="POST",
        headers={
            "cookie": f"session={ctx.sid}",
            "x-csrf-token": "token",
            "content-type": "application/x-www-form-urlencoded",
        },
        body=b"login_type=password&identifier=new&password=p&auth_code=C",
    )
    assert response.status == 409
    assert not store.sessions
    assert "Max-Age=0" in " ".join(response.header("set-cookie"))


def test_login_page_bootstraps_csrf(monkeypatch: MonkeyPatch, tmp_path):
    _install_fake_store(monkeypatch)
    (tmp_path / "login.html").write_text("login", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIST_DIR", tmp_path)
    response = invoke("/")
    assert response.status == 200
    cookies = " ".join(response.header("set-cookie"))
    assert "session=" in cookies and "csrf_token=" in cookies
