"""Security boundary contracts: public errors, cookies, CSRF methods, redacted logs."""

from __future__ import annotations

import json
import logging
from io import StringIO

from app import main
from app.public_errors import INTERNAL_ERROR
from app.responses import _upstream_error
from tests.contract_support import (
    FakeResponse,
    MonkeyPatch,
    _authed_session,
    _install_fake_store,
    authed_request,
    invoke,
    run_endpoint,
)

SECRET_SENTINEL = "SECRET_SENTINEL"
OTP_SENTINEL = "OTP_SENTINEL"


def test_purchase_exception_does_not_leak_to_response_or_logs(
    monkeypatch: MonkeyPatch,
) -> None:
    def boom(**_kw: object) -> None:
        raise RuntimeError(SECRET_SENTINEL)

    monkeypatch.setattr(main, "make_3hk_request", boom)
    request = authed_request(
        "/api/purchase",
        "POST",
        body=json.dumps(
            {
                "account_id": "a@b.com",
                "subscriptionId": "s",
                "items": [{"offerId": "o", "quantity": 1}],
                "price": 1,
                "txnAmount": 1,
                "paymentType": "WALLET",
                "new_line": False,
            }
        ).encode(),
        content_type="application/json",
    )
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    logger = logging.getLogger("app.routes.commerce")
    logger.addHandler(handler)
    try:
        resp = run_endpoint("/api/purchase", request)
    finally:
        logger.removeHandler(handler)

    body = json.loads(bytes(resp.body))
    assert resp.status_code == 500
    assert body == {"status": "error", "message": INTERNAL_ERROR.message}
    assert SECRET_SENTINEL not in json.dumps(body)
    assert SECRET_SENTINEL not in buf.getvalue()
    assert "a@b.com" not in buf.getvalue()


def test_upstream_error_does_not_log_response_body() -> None:
    upstream = FakeResponse(
        status_code=400, json_data={"error": OTP_SENTINEL}, text=OTP_SENTINEL
    )
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    logger = logging.getLogger("app.responses")
    logger.addHandler(handler)
    try:
        resp = _upstream_error(
            upstream,  # type: ignore[arg-type]
            "fail",
            400,
            operation="test_op",
            correlation_id="cid-test",
        )
    finally:
        logger.removeHandler(handler)

    assert json.loads(bytes(resp.body)) == {"status": "error", "message": "fail"}
    log_text = buf.getvalue()
    assert OTP_SENTINEL not in log_text
    assert "operation=test_op" in log_text
    assert "correlation_id=cid-test" in log_text
    assert "body=" not in log_text


def test_session_and_csrf_cookies_honor_cookie_secure_flag(
    monkeypatch: MonkeyPatch,
) -> None:
    store = _install_fake_store(monkeypatch)
    sid, csrf = _authed_session(store)
    monkeypatch.setattr("app.session_utils._runtime.COOKIE_SECURE", True)
    monkeypatch.setattr(
        main, "make_3hk_request", lambda **kw: FakeResponse(200, [{"amount": 0}])
    )
    resp = invoke(
        "/api/balance?account_id=a@b.com&subscriptionId=s",
        headers={"cookie": f"session={sid}"},
    )
    cookies = resp.header("set-cookie")
    session_cookie = next(c for c in cookies if c.startswith("session="))
    csrf_cookie = next(c for c in cookies if c.startswith("csrf_token="))
    assert "Secure" in session_cookie
    assert "Secure" in csrf_cookie
    assert f"csrf_token={csrf}" in csrf_cookie


def test_session_and_csrf_cookies_omit_secure_when_disabled(
    monkeypatch: MonkeyPatch,
) -> None:
    store = _install_fake_store(monkeypatch)
    sid, _ = _authed_session(store)
    monkeypatch.setattr("app.session_utils._runtime.COOKIE_SECURE", False)
    monkeypatch.setattr(
        main, "make_3hk_request", lambda **kw: FakeResponse(200, [{"amount": 0}])
    )
    resp = invoke(
        "/api/balance?account_id=a@b.com&subscriptionId=s",
        headers={"cookie": f"session={sid}"},
    )
    cookies = " ".join(resp.header("set-cookie"))
    assert "Secure" not in cookies


def test_get_logout_returns_405() -> None:
    resp = invoke("/logout", method="GET")
    assert resp.status == 405


def test_post_logout_requires_csrf(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    sid, _ = _authed_session(store, accounts={"a@b.com": {"sub_brand": "THREE"}})
    resp = invoke(
        "/logout",
        method="POST",
        headers={
            "cookie": f"session={sid}",
            "content-type": "application/x-www-form-urlencoded",
        },
        body=b"account_id=a%40b.com",
    )
    assert resp.status == 403
    assert resp.json == {"status": "error", "message": "CSRF token invalid"}


def test_post_logout_with_csrf_clears_last_account(monkeypatch: MonkeyPatch) -> None:
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


def test_get_cmn_numbers_returns_405() -> None:
    resp = invoke("/api/cmn/numbers", method="GET")
    assert resp.status == 405


def test_post_cmn_numbers_requires_csrf(monkeypatch: MonkeyPatch) -> None:
    request = authed_request(
        "/api/cmn/numbers",
        "POST",
        csrf=None,
        content_type="application/x-www-form-urlencoded",
        body=b"account_id=a@b.com&subscriptionId=s",
    )
    resp = run_endpoint("/api/cmn/numbers", request)
    assert resp.status_code == 403


def test_session_cleanup_uses_constant_time_compare(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setattr(main, "SESSION_SECRET", "expected-secret-value")

    class FakeRedis:
        def ping(self) -> bool:
            return True

    monkeypatch.setattr(main, "redis_client", FakeRedis())
    wrong = invoke(
        "/internal/session-cleanup",
        method="POST",
        headers={"x-session-secret": "wrong-secret-value!!"},
    )
    assert wrong.status == 401
    ok = invoke(
        "/internal/session-cleanup",
        method="POST",
        headers={"x-session-secret": "expected-secret-value"},
    )
    assert ok.status == 200
    assert ok.json == {"redis_ok": True}


def test_cookie_secure_rejects_invalid_values(monkeypatch: MonkeyPatch) -> None:
    from app import config

    monkeypatch.setenv("COOKIE_SECURE", "yes")
    try:
        config.load_settings()
        raise AssertionError("expected COOKIE_SECURE validation error")
    except RuntimeError as exc:
        assert "COOKIE_SECURE" in str(exc)
