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
    assert body == {
        "status": "error",
        "message": INTERNAL_ERROR.message,
        "code": INTERNAL_ERROR.code,
    }
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
            upstream,
            "fail",
            400,
            operation="test_op",
            correlation_id="cid-test",
        )
    finally:
        logger.removeHandler(handler)

    assert json.loads(bytes(resp.body)) == {
        "status": "error",
        "message": "fail",
        "code": "upstream_error",
    }
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
    assert resp.json == {
        "status": "error",
        "message": "CSRF token invalid",
        "code": "csrf_invalid",
    }


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


def test_public_error_includes_stable_code() -> None:
    from app.public_errors import INVALID_REQUEST
    from app.responses import _public_error

    resp = _public_error(INVALID_REQUEST, 400)
    assert resp.status_code == 400
    assert json.loads(bytes(resp.body)) == {
        "status": "error",
        "message": INVALID_REQUEST.message,
        "code": "invalid_request",
    }


def test_malformed_json_returns_invalid_request(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    sid, csrf = _authed_session(store)
    resp = invoke(
        "/api/purchase",
        method="POST",
        headers={
            "cookie": f"session={sid}",
            "x-csrf-token": csrf,
            "content-type": "application/json",
        },
        body=b"{not-json",
    )
    assert resp.status == 400
    assert resp.json == {
        "status": "error",
        "message": "请求参数无效",
        "code": "invalid_request",
    }


def test_openapi_documents_logout_and_cmn_form_and_csrf_header() -> None:
    paths = main.app.openapi()["paths"]
    assert "get" not in paths["/logout"]
    logout = paths["/logout"]["post"]
    logout_blob = str(logout)
    assert "x-csrf-token" in logout_blob
    assert "account_id" in logout_blob
    assert "application/x-www-form-urlencoded" in logout_blob

    assert "get" not in paths["/api/cmn/numbers"]
    cmn = paths["/api/cmn/numbers"]["post"]
    cmn_blob = str(cmn)
    assert "x-csrf-token" in cmn_blob
    assert "subscriptionId" in cmn_blob
    assert "application/x-www-form-urlencoded" in cmn_blob


def test_logout_ignores_query_account_id(monkeypatch: MonkeyPatch) -> None:
    store = _install_fake_store(monkeypatch)
    sid, csrf = _authed_session(
        store,
        accounts={
            "first@x.com": {"sub_brand": "THREE"},
            "second@x.com": {"sub_brand": "SOSIM"},
        },
    )
    # Query-only account_id must not remove second account
    resp = invoke(
        "/logout?account_id=second%40x.com",
        method="POST",
        headers={
            "cookie": f"session={sid}",
            "x-csrf-token": csrf,
            "content-type": "application/x-www-form-urlencoded",
        },
        body=b"",
    )
    assert resp.status == 302
    assert resp.header("location") == ["/"]
    assert sid not in store.sessions


def test_upstream_logging_redacts_account_identifier() -> None:
    from starlette.requests import Request

    from app import main as main_mod
    from app import upstream
    from app.session_store import SessionContext

    account_id = SECRET_SENTINEL
    ctx = SessionContext(
        sid="sid-x",
        data={
            "accounts": {
                account_id: {
                    "cookies": {},
                    "login_type": "password",
                    "stored_password_encrypted": "enc",
                    "sub_brand": "THREE",
                }
            }
        },
    )
    account_data = ctx.data["accounts"][account_id]

    class BoomSession:
        def __enter__(self) -> BoomSession:
            return self

        def __exit__(self, *_args: object) -> None:
            return None

        def post(self, *_a: object, **_k: object) -> object:
            raise RuntimeError(OTP_SENTINEL)

    class Deps:
        decrypt_password = staticmethod(lambda _v: "pw")
        get_isolated_session = staticmethod(lambda: BoomSession())
        _save_session = staticmethod(lambda _ctx: None)
        resolve_proxies = staticmethod(lambda url, proxies: proxies)
        attempt_silent_relogin = staticmethod(lambda *_a, **_k: False)
        get_account_context = staticmethod(lambda *_a, **_k: None)
        make_3hk_request = staticmethod(lambda **_k: None)

    previous = upstream._upstream_deps_provider
    upstream.configure_upstream_deps(lambda: Deps())  # noqa: SLF001
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    logger = logging.getLogger("app.upstream")
    logger.addHandler(handler)
    try:
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/",
                "headers": [],
                "query_string": b"",
            }
        )
        ok = upstream.attempt_silent_relogin(request, ctx, account_id, account_data)
        assert ok is False
    finally:
        logger.removeHandler(handler)
        if previous is not None:
            upstream.configure_upstream_deps(previous)
        else:
            main_mod.configure_upstream_deps(lambda: main_mod._main_deps)

    log_text = buf.getvalue()
    assert SECRET_SENTINEL not in log_text
    assert OTP_SENTINEL not in log_text
    assert "error_class=RuntimeError" in log_text


def test_session_store_logging_redacts_sid_and_exception() -> None:
    from redis.exceptions import RedisError

    from app.session_store import RedisSessionStore

    class Boom:
        def get(self, name: str) -> None:
            raise RedisError(SECRET_SENTINEL)

        def setex(self, name: str, time: int, value: str) -> None:
            raise RedisError(SECRET_SENTINEL)

        def delete(self, *names: str) -> int:
            raise RedisError(SECRET_SENTINEL)

    store = RedisSessionStore(
        Boom(), key_prefix="session:", lifetime_seconds=60, sid_prefix="3hk_"
    )
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    logger = logging.getLogger("app.session_store")
    logger.addHandler(handler)
    try:
        assert store.load(SECRET_SENTINEL) is None
        try:
            store.save(SECRET_SENTINEL, {"a": 1})
        except RuntimeError:
            pass
        try:
            store.delete(SECRET_SENTINEL)
        except RuntimeError:
            pass
    finally:
        logger.removeHandler(handler)
    log_text = buf.getvalue()
    assert SECRET_SENTINEL not in log_text
    assert "error_class=RedisError" in log_text


def test_auth_code_store_logging_redacts_code_and_exception(
    tmp_path: object,
) -> None:
    from pathlib import Path

    from redis.exceptions import RedisError

    from app.auth_codes import AuthCodeStore

    class Boom:
        def exists(self, *names: str) -> int:
            raise RedisError(SECRET_SENTINEL)

        def hset(self, *a: object, **k: object) -> None:
            raise RedisError(SECRET_SENTINEL)

        def delete(self, *names: str) -> int:
            return 0

        def scan_iter(self, match: str | None = None):
            return []

        def hgetall(self, name: str) -> dict[str, str]:
            raise RedisError(SECRET_SENTINEL)

        def eval(self, *a: object, **k: object) -> object:
            raise RedisError(SECRET_SENTINEL)

    seed = Path(str(tmp_path)) / "auth_codes.json"
    seed.write_text(
        json.dumps({SECRET_SENTINEL: {"usage_limit": 1, "times_used": 0}}),
        encoding="utf-8",
    )
    store = AuthCodeStore(Boom(), seed_file=seed)
    buf = StringIO()
    handler = logging.StreamHandler(buf)
    logger = logging.getLogger("app.auth_codes")
    logger.addHandler(handler)
    try:
        store.seed_from_file()
        ok, _msg = store.verify(SECRET_SENTINEL, consume=False)
        assert ok is False
    finally:
        logger.removeHandler(handler)
    log_text = buf.getvalue()
    assert SECRET_SENTINEL not in log_text
    assert "error_class=RedisError" in log_text
