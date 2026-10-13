from __future__ import annotations

import json
from pathlib import Path

from app import main
from tests.contract_support import (
    FakeResponse,
    MonkeyPatch,
    _authed_session,
    _install_fake_store,
    authed_request,
    invoke,
    run_endpoint,
)


def test_index_redirects_to_first_account_when_logged_in(
    monkeypatch: MonkeyPatch,
) -> None:
    store = _install_fake_store(monkeypatch)
    sid, _ = _authed_session(
        store,
        accounts={
            "first@x.com": {"sub_brand": "THREE"},
            "second@x.com": {"sub_brand": "SOSIM"},
        },
    )
    resp = invoke("/", headers={"cookie": f"session={sid}"})
    assert resp.status == 302
    assert resp.header("location") == ["/main/first@x.com"]


def test_index_serves_login_html_for_add_query(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    _install_fake_store(monkeypatch)
    login_html = tmp_path / "login.html"
    login_html.write_text("<html>fixture login</html>", encoding="utf-8")
    monkeypatch.setattr(main, "FRONTEND_DIST_DIR", tmp_path)

    resp = invoke("/?add=1")
    assert resp.status == 200
    assert resp.header("content-type") and "text/html" in resp.header("content-type")[0]
    assert bytes(resp.body) == b"<html>fixture login</html>"


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


def test_anonymous_request_sets_no_session_or_csrf_cookie() -> None:
    resp = invoke("/_health")
    set_cookie = resp.header("set-cookie")
    assert not any(c.startswith("session=") for c in set_cookie)
    assert not any(c.startswith("csrf_token=") for c in set_cookie)


def test_stale_session_cookie_is_deleted(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    resp = invoke(
        "/api/balance?account_id=a@b.com", headers={"cookie": "session=ghost"}
    )
    set_cookie = " ".join(resp.header("set-cookie"))
    assert "session=" in set_cookie and "Max-Age=0" in set_cookie
    assert "csrf_token=" in set_cookie and "Max-Age=0" in set_cookie


def test_logged_in_session_sets_session_and_csrf_cookies(
    monkeypatch: MonkeyPatch,
) -> None:
    store = _install_fake_store(monkeypatch)
    sid, csrf = _authed_session(store)
    monkeypatch.setattr(
        main, "make_3hk_request", lambda **kw: FakeResponse(200, [{"amount": 0}])
    )
    resp = invoke(
        "/api/balance?account_id=a@b.com&subscriptionId=s",
        headers={"cookie": f"session={sid}"},
    )
    cookies = resp.header("set-cookie")
    session_cookie = [c for c in cookies if c.startswith("session=")][0]
    csrf_cookie = [c for c in cookies if c.startswith("csrf_token=")][0]
    assert f"session={sid}" in session_cookie
    assert f"csrf_token={csrf}" in csrf_cookie
    assert "HttpOnly" in session_cookie
    assert "SameSite=lax" in session_cookie
    assert "Path=/" in session_cookie
    assert "HttpOnly" not in csrf_cookie
    assert "SameSite=lax" in csrf_cookie


def test_plans_invalid_account_returns_401_bare_error(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    request = authed_request(
        "/api/plans", "GET", accounts={"other@x.com": {"cookies": {}}}
    )
    request.scope["query_string"] = b"account_id=missing@x.com"
    resp = run_endpoint("/api/plans", request)
    assert resp.status_code == 401
    assert json.loads(bytes(resp.body)) == {"status": "error"}


def test_plans_serves_cached_brand_file(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    (tmp_path / "plans_THREE.json").write_text(
        json.dumps({"status": "success", "plans": [{"offerId": "fixture-plan"}]}),
        encoding="utf-8",
    )
    monkeypatch.setattr(main, "PLANS_CACHE_DIR", tmp_path)
    monkeypatch.setattr(main, "fetch_and_save_plans_background", lambda *a, **k: None)
    request = authed_request("/api/plans", "GET")
    request.scope["query_string"] = b"account_id=a@b.com&subscriptionId=s&brand=THREE"
    resp = run_endpoint("/api/plans", request)
    assert resp.status_code == 200
    body = json.loads(bytes(resp.body))
    assert body["status"] == "success"
    assert body["plans"] == [{"offerId": "fixture-plan"}]


def test_logout_no_session_redirects_to_root(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    resp = invoke("/logout", method="POST")
    assert resp.status == 302
    assert resp.header("location") == ["/"]


def test_logout_last_account_clears_session(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    sid, csrf = _authed_session(store, accounts={"a@b.com": {"sub_brand": "THREE"}})
    resp = invoke(
        "/logout",
        method="POST",
        headers={
            "cookie": f"session={sid}",
            "x-csrf-token": csrf,
            "content-type": "application/x-www-form-urlencoded",
        },
        body=b"account_id=a%40b.com",
    )
    assert resp.status == 302
    assert resp.header("location") == ["/"]
    assert sid not in store.sessions
    set_cookie = " ".join(resp.header("set-cookie"))
    assert "Max-Age=0" in set_cookie


def test_logout_remaining_account_redirects_to_first(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    sid, csrf = _authed_session(
        store,
        accounts={
            "first@x.com": {"sub_brand": "THREE"},
            "second@x.com": {"sub_brand": "SOSIM"},
        },
    )
    resp = invoke(
        "/logout",
        method="POST",
        headers={
            "cookie": f"session={sid}",
            "x-csrf-token": csrf,
            "content-type": "application/x-www-form-urlencoded",
        },
        body=b"account_id=second%40x.com",
    )
    assert resp.status == 302
    assert resp.header("location") == ["/main/first@x.com"]
    assert sid in store.sessions
    assert "second@x.com" not in store.sessions[sid]["accounts"]


def test_session_cleanup_wrong_secret_returns_401(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    resp = invoke(
        "/internal/session-cleanup",
        method="POST",
        headers={"x-session-secret": "wrong"},
    )
    assert resp.status == 401
    assert resp.json == {
        "status": "error",
        "message": "Unauthorized",
        "code": "unauthorized",
    }


def test_health_returns_ok() -> None:
    resp = invoke("/_health")
    assert resp.status == 200
    assert resp.json == {"status": "ok"}


def test_favicon_serves_existing_frontend_png(
    monkeypatch: MonkeyPatch,
    tmp_path: Path,
) -> None:
    icon = tmp_path / "static" / "images" / "icon-192.png"
    icon.parent.mkdir(parents=True)
    icon_bytes = b"\x89PNG\r\n\x1a\nfixture-icon"
    icon.write_bytes(icon_bytes)
    monkeypatch.setattr(main, "FRONTEND_DIST_DIR", tmp_path)

    resp = invoke("/favicon.ico")

    assert resp.status == 200
    assert resp.header("content-type") == ["image/png"]
    assert bytes(resp.body) == icon_bytes


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


def test_metrics_missing_secret_returns_404() -> None:
    resp = invoke("/metrics")
    assert resp.status == 404


def test_metrics_wrong_secret_returns_403(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(main, "METRICS_SECRET", "expected-secret")
    resp = invoke("/metrics", headers={"x-metrics-secret": "wrong"})
    assert resp.status == 403
    assert resp.json["code"] == "unauthorized"


def test_metrics_correct_secret_returns_prometheus_text(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "METRICS_SECRET", "expected-secret")
    # generate some traffic first
    invoke("/_health")
    resp = invoke("/metrics", headers={"x-metrics-secret": "expected-secret"})
    assert resp.status == 200
    body = (
        resp.body.decode("utf-8")
        if isinstance(resp.body, (bytes, bytearray))
        else str(resp.body)
    )
    assert "http_requests_total" in body
    assert "SENTINEL_PII_should_not_appear" not in body


def test_metrics_excludes_pii_from_labels(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(main, "METRICS_SECRET", "expected-secret")
    # Hit a path that looks like an account id (will 302/redirect or 404 without session)
    invoke("/main/user@pii-example.com")
    resp = invoke(
        "/metrics",
        headers={"x-metrics-secret": "expected-secret"},
    )
    assert resp.status == 200
    body = (
        resp.body.decode("utf-8")
        if isinstance(resp.body, (bytes, bytearray))
        else str(resp.body)
    )
    assert "user@pii-example.com" not in body
    assert "pii-example" not in body
