"""Contract tests: logout, session-cleanup, health, readiness."""

from __future__ import annotations

from pytest import MonkeyPatch

from app import main
from tests.contract_helpers import (
    _authed_session,
    _install_fake_store,
    invoke,
)


def test_logout_no_session_redirects_to_root(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    resp = invoke("/logout")
    assert resp.status == 302
    assert resp.header("location") == ["/"]


def test_logout_last_account_clears_session(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    sid, _ = _authed_session(store, accounts={"a@b.com": {"sub_brand": "THREE"}})
    resp = invoke("/logout?account_id=a@b.com", headers={"cookie": f"session={sid}"})
    assert resp.status == 302
    assert resp.header("location") == ["/"]
    # session deleted from store
    assert sid not in store.sessions
    # cookies marked for deletion
    set_cookie = " ".join(resp.header("set-cookie"))
    assert "Max-Age=0" in set_cookie


def test_logout_remaining_account_redirects_to_first(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    sid, _ = _authed_session(store, accounts={"first@x.com": {"sub_brand": "THREE"}, "second@x.com": {"sub_brand": "SOSIM"}})
    resp = invoke("/logout?account_id=second@x.com", headers={"cookie": f"session={sid}"})
    assert resp.status == 302
    assert resp.header("location") == ["/main/first@x.com"]
    # session still alive
    assert sid in store.sessions
    assert "second@x.com" not in store.sessions[sid]["accounts"]

def test_session_cleanup_wrong_secret_returns_401(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    resp = invoke("/internal/session-cleanup", method="POST", headers={"x-session-secret": "wrong"})
    assert resp.status == 401
    assert resp.json == {"status": "error", "message": "Unauthorized"}

def test_health_returns_ok() -> None:
    resp = invoke("/_health")
    assert resp.status == 200
    assert resp.json == {"status": "ok"}


def test_readiness_reports_checks_shape(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(main.redis_client, "ping", lambda: True)
    resp = invoke("/_ready")
    assert resp.status in (200, 503)
    body = resp.json
    assert body["status"] in ("ok", "error")
    checks = body["checks"]
    for key in [
        "redis",
        "frontend_index",
        "frontend_login",
        "frontend_assets",
        "frontend_manifest",
        "frontend_sw",
        "plans_cache_dir",
    ]:
        assert key in checks
    assert checks["redis"] is True

