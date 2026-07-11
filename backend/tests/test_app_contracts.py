"""Backend route contract tests (characterization).

Locks the externally observable behavior of every public route: auth gating
(302 redirects), status codes, JSON response shapes, CSRF enforcement, the
session/csrf cookie attributes set by SessionMiddleware, and cache invalidation
on purchase/transfer/logout.

Two execution strategies are used, both Redis-free and network-free:

* ASGI driver — runs the real FastAPI app end to end (middleware included) so
  that cookie/CSRF/redirect behavior is exercised faithfully. ``session_store``
  is swapped for an in-memory fake and upstream calls are stubbed.

* Direct endpoint invocation — builds a starlette Request with a form/json body
  and runs the endpoint coroutine directly (like the pre-existing
  ``test_app_routes.py``), stubbing the session via ``request.state``.

No production behavior is changed by these tests.
"""

from __future__ import annotations

import json
from collections.abc import Sequence
from typing import Any, Callable

import anyio
import requests
from fastapi.routing import APIRoute
from pytest import MonkeyPatch
from starlette.requests import Request
from starlette.types import Message, Scope

from app import main
from app.session_store import SessionContext

SESSION_COOKIE_NAME = "session"
CSRF_COOKIE_NAME = "csrf_token"
CSRF_HEADER_NAME = "x-csrf-token"


# =========================================================================
# Fakes
# =========================================================================


class FakeResponse:
    def __init__(
        self,
        status_code: int = 200,
        json_data: Any = None,
        cookies: dict[str, str] | None = None,
        text: str = "",
    ) -> None:
        self.status_code = status_code
        self._json = json_data if json_data is not None else {}
        self.cookies = requests.utils.cookiejar_from_dict(cookies or {})
        self.text = text

    def json(self) -> Any:
        return self._json


class FakeSessionStore:
    """In-memory stand-in for RedisSessionStore."""

    def __init__(self) -> None:
        self.sessions: dict[str, dict[str, Any]] = {}
        self._n = 0

    def load(self, sid: str) -> dict[str, Any] | None:
        return self.sessions.get(sid)

    def save(self, sid: str, data: dict[str, Any]) -> None:
        self.sessions[sid] = data

    def create(self, data: dict[str, Any]) -> SessionContext:
        self._n += 1
        sid = f"3hk_user_fake-{self._n}"
        self.sessions[sid] = data
        return SessionContext(sid=sid, data=data)

    def delete(self, sid: str) -> None:
        self.sessions.pop(sid, None)


class FakeIsolatedSession:
    """Mimics the requests.Session context-manager used in the login flow.

    The login handler opens two separate isolated sessions (one for the
    existingCustDipping check, one for the actual login), so each session only
    ever performs a single request. Callers hand out one response per session
    via :func:`isolated_sessions`.
    """

    def __init__(self, response: FakeResponse) -> None:
        self._response = response
        self.cookies = requests.utils.cookiejar_from_dict({})

    def __enter__(self) -> "FakeIsolatedSession":
        return self

    def __exit__(self, *_: object) -> None:
        return None

    def post(self, url, json=None, headers=None, proxies=None, timeout=None, **_):
        return self._response

    def get(self, url, headers=None, proxies=None, timeout=None, **_):
        return self._response


def isolated_sessions(responses: list[FakeResponse]) -> Callable[[], FakeIsolatedSession]:
    """Build a get_isolated_session substitute returning one response per call."""
    queue = list(responses)

    def factory() -> FakeIsolatedSession:
        return FakeIsolatedSession(queue.pop(0) if queue else FakeResponse(204))

    return factory


# =========================================================================
# Fixtures
# =========================================================================


def _seeded_ctx(
    accounts: dict[str, Any] | None = None,
    csrf: str = "tok",
    sid: str = "sid-seeded",
) -> SessionContext:
    return SessionContext(
        sid=sid,
        data={"csrf_token": csrf, "accounts": accounts or {}},
    )


def _install_fake_store(monkeypatch: MonkeyPatch) -> FakeSessionStore:
    store = FakeSessionStore()
    monkeypatch.setattr(main, "session_store", store)
    return store


# =========================================================================
# ASGI driver — drives the real app (middleware included)
# =========================================================================


class ASGIResponse:
    def __init__(self, messages: Sequence[Message]) -> None:
        self.status: int | None = None
        self.headers: list[tuple[bytes, bytes]] = []
        self.body = b""
        for msg in messages:
            if msg["type"] == "http.response.start":
                self.status = msg["status"]
                self.headers = list(msg.get("headers", []))
            elif msg["type"] == "http.response.body":
                self.body += msg.get("body", b"")

    def header(self, name: str) -> list[str]:
        nl = name.lower()
        return [v.decode() for k, v in self.headers if k.decode() == nl]

    @property
    def json(self) -> Any:
        return json.loads(self.body) if self.body else None


def invoke(
    path: str,
    method: str = "GET",
    *,
    headers: dict[str, str] | None = None,
    body: bytes = b"",
    query: bytes = b"",
) -> ASGIResponse:
    """Drive the real ASGI app; returns the collected response.

    A query string embedded in ``path`` (``/x?a=1``) is honored so callers can
    keep using natural-looking paths.
    """

    if "?" in path:
        base, _, qs = path.partition("?")
        raw_path = base.encode()
        query = query or qs.encode()
    else:
        raw_path = path.encode()

    raw_headers = [(k.lower().encode(), v.encode()) for k, v in (headers or {}).items()]
    if body and not any(k == b"content-type" for k, _ in raw_headers):
        raw_headers.append((b"content-type", b"application/json"))

    done = {"flag": False}

    async def receive() -> Message:
        if done["flag"]:
            return {"type": "http.disconnect"}
        done["flag"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    messages: list[Message] = []

    async def send(message: Message) -> None:
        messages.append(message)

    scope: Scope = {
        "type": "http",
        "method": method,
        "path": raw_path.decode(),
        "raw_path": raw_path,
        "root_path": "",
        "query_string": query,
        "headers": raw_headers,
        "client": ("127.0.0.1", 8000),
        "server": ("127.0.0.1", 8000),
        "scheme": "http",
        "http_version": "1.1",
        "app": main.app,
    }

    anyio.run(main.app, scope, receive, send)
    return ASGIResponse(messages)


def _authed_session(
    store: FakeSessionStore,
    *,
    csrf: str = "tok",
    sid: str = "sid-seeded",
    accounts: dict[str, Any] | None = None,
) -> tuple[str, str]:
    """Seed the fake store with a logged-in session; returns (sid, csrf)."""
    store.sessions[sid] = {
        "csrf_token": csrf,
        "accounts": accounts or {"a@b.com": {"cookies": {}, "sub_brand": "THREE"}},
    }
    return sid, csrf


# =========================================================================
# Direct endpoint invocation helpers
# =========================================================================


def build_request(
    method: str,
    path: str,
    *,
    headers: dict[str, str] | None = None,
    query: bytes = b"",
    body: bytes = b"",
    content_type: str | None = None,
    cookies: dict[str, str] | None = None,
) -> Request:
    raw_headers: list[tuple[bytes, bytes]] = []
    if content_type:
        raw_headers.append((b"content-type", content_type.encode()))
    for k, v in (headers or {}).items():
        raw_headers.append((k.encode(), v.encode()))
    if cookies:
        cookie_str = "; ".join(f"{k}={v}" for k, v in cookies.items())
        raw_headers.append((b"cookie", cookie_str.encode()))

    done = {"flag": False}

    async def receive() -> Message:
        if done["flag"]:
            return {"type": "http.disconnect"}
        done["flag"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    async def send(_message: Message) -> None:  # noqa: ARG001
        return None

    scope: Scope = {
        "type": "http",
        "method": method,
        "path": path,
        "headers": raw_headers,
        "query_string": query,
    }
    return Request(scope, receive=receive, send=send)


def _endpoint(path: str) -> Callable[..., Any]:
    for route in main.app.routes:
        if isinstance(route, APIRoute) and route.path == path:
            endpoint = route.endpoint
            if callable(endpoint):
                return endpoint
    raise AssertionError(f"route {path} not found")


def run_endpoint(path: str, request: Request) -> Any:
    return anyio.run(_endpoint(path), request)


def authed_request(
    path: str,
    method: str,
    *,
    accounts: dict[str, Any] | None = None,
    csrf: str | None = "tok",
    headers: dict[str, str] | None = None,
    query: bytes = b"",
    body: bytes = b"",
    content_type: str | None = None,
) -> Request:
    """Build a request with an attached (logged-in) session via request.state."""
    request_headers = dict(headers or {})
    if csrf is not None:
        request_headers[CSRF_HEADER_NAME] = csrf
    req = build_request(
        method,
        path,
        headers=request_headers,
        query=query,
        body=body,
        content_type=content_type,
    )
    ctx = _seeded_ctx(accounts=accounts or {"a@b.com": {"cookies": {}, "sub_brand": "THREE"}})
    req.state.session_ctx = ctx
    return req


# =========================================================================
# Auth gating & redirects (ASGI driver)
# =========================================================================


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


# =========================================================================
# /login contracts (ASGI driver)
# =========================================================================


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


# =========================================================================
# /api/profile contracts (direct invocation)
# =========================================================================


def _profile_upstream(brand: str, mobile: str = "85212345678") -> dict[str, Any]:
    return {
        "email": "a@b.com" if brand == "THREE" else "",
        "subscriptions": [
            {
                "primaryMsisdn": mobile,
                "subscriptionId": "sub-1",
                "activationDate": "2024-01-01T00:00:00",
                "subsEndDate": "2025-01-01T00:00:00",
                "iccid": "icc",
                "status": "ACTIVE",
                "subscriptionOffers": [
                    {
                        "offerId": "OFF1",
                        "offerType": "VAS",
                        "offerSubType": "LOCAL",
                        "planStatus": "ACTIVE",
                        "transferAllowed": False,
                        "subscriptionProducts": [
                            {
                                "productName": "Data Pack",
                                "productSpecType": "DATA",
                                "transferAllowed": False,
                                "minTransferQuota": 0,
                                "matrixxBalanceInfos": [
                                    {"unit": "MB", "grantAmount": 1000, "amount": 400, "resourceId": "r1"}
                                ],
                            }
                        ],
                    }
                ],
            }
        ],
    }


def test_profile_missing_account_id_returns_400(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    request = authed_request("/api/profile", "GET")
    resp = run_endpoint("/api/profile", request)
    assert resp.status_code == 400
    assert json.loads(bytes(resp.body)) == {"status": "error", "message": "Missing account_id"}


def test_profile_invalid_account_returns_401(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    request = authed_request("/api/profile", "GET", accounts={"other@x.com": {"cookies": {}}})
    request.scope["query_string"] = b"account_id=missing@x.com"
    resp = run_endpoint("/api/profile", request)
    assert resp.status_code == 401
    assert json.loads(bytes(resp.body)) == {"status": "error", "message": "Invalid account"}


def test_profile_returns_cached_without_upstream_call(monkeypatch: MonkeyPatch) -> None:
    calls: list[str] = []
    monkeypatch.setattr(main, "get_cache", lambda k: {"status": "success", "data": {"cached": True}} if k == "profile_a@b.com" else None)
    monkeypatch.setattr(main, "set_cache", lambda *a, **k: calls.append("set"))
    request = authed_request("/api/profile", "GET")
    request.scope["query_string"] = b"account_id=a@b.com"
    resp = run_endpoint("/api/profile", request)
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body)) == {"status": "success", "data": {"cached": True}}


def test_profile_refresh_deletes_cache_then_fetches(monkeypatch: MonkeyPatch) -> None:
    deleted: list[str] = []
    cache_box: dict[str, Any] = {"profile_a@b.com": {"status": "success", "old": True}}

    def fake_get(key):
        return cache_box.get(key)

    def fake_delete(key):
        cache_box.pop(key, None)
        deleted.append(key)

    monkeypatch.setattr(main, "get_cache", fake_get)
    monkeypatch.setattr(main, "delete_cache", fake_delete)
    fetched: list[str] = []

    def fake_make(**kw):
        fetched.append(kw.get("url", ""))
        return FakeResponse(200, _profile_upstream("THREE"))

    monkeypatch.setattr(main, "make_3hk_request", fake_make)
    monkeypatch.setattr(main, "set_cache", lambda *a, **k: None)

    request = authed_request("/api/profile", "GET")
    request.scope["query_string"] = b"account_id=a@b.com&refresh=true"
    resp = run_endpoint("/api/profile", request)
    assert resp.status_code == 200
    body = json.loads(bytes(resp.body))
    assert body["status"] == "success"
    assert deleted == ["profile_a@b.com"]
    assert fetched  # upstream re-fetched after cache invalidation


def test_profile_aggregates_offers_and_caches(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(main, "get_cache", lambda k: None)
    set_calls: list[tuple[str, Any]] = []
    monkeypatch.setattr(main, "set_cache", lambda key, value, timeout=300: set_calls.append((key, value)))

    def fake_make(**kw):
        return FakeResponse(200, _profile_upstream("THREE"))

    monkeypatch.setattr(main, "make_3hk_request", fake_make)
    request = authed_request("/api/profile", "GET")
    request.scope["query_string"] = b"account_id=a@b.com"
    resp = run_endpoint("/api/profile", request)
    assert resp.status_code == 200
    body = json.loads(bytes(resp.body))
    assert body["data"]["email"] == "a@b.com"
    sub = body["data"]["subscriptions"][0]
    assert sub["mobile"] == "85212345678"
    assert sub["brand"] == "THREE"
    offer = sub["activeOffers"][0]
    assert offer["offerId"] == "OFF1"
    assert offer["usage"][0]["unit"] == "MB"
    assert offer["usage"][0]["total"] == 1000
    assert offer["usage"][0]["remain"] == 400
    assert body["data"]["current"]["mobile"] == "85212345678"
    assert set_calls and set_calls[0][0] == "profile_a@b.com"


# =========================================================================
# /api/balance contracts (direct invocation)
# =========================================================================


def test_balance_no_account_returns_zero(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    request = authed_request("/api/balance", "GET", accounts={"other@x.com": {"cookies": {}}})
    request.scope["query_string"] = b"account_id=missing@x.com&subscriptionId=s"
    resp = run_endpoint("/api/balance", request)
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body)) == {"status": "success", "balance": 0}


def test_balance_returns_max_amount(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(main, "make_3hk_request", lambda **kw: FakeResponse(200, [{"amount": 5}, {"amount": 88.5}]))
    request = authed_request("/api/balance", "GET")
    request.scope["query_string"] = b"account_id=a@b.com&subscriptionId=s"
    resp = run_endpoint("/api/balance", request)
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body)) == {"status": "success", "balance": 88.5}


def test_balance_upstream_error_returns_zero(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(main, "make_3hk_request", lambda **kw: (_ for _ in ()).throw(RuntimeError("x")))
    request = authed_request("/api/balance", "GET")
    request.scope["query_string"] = b"account_id=a@b.com&subscriptionId=s"
    resp = run_endpoint("/api/balance", request)
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body)) == {"status": "success", "balance": 0}


# =========================================================================
# /api/purchase contracts (direct invocation)
# =========================================================================


def _purchase_request(body: dict[str, Any], csrf: str | None = "tok") -> Request:
    return authed_request(
        "/api/purchase",
        "POST",
        headers={CSRF_HEADER_NAME: csrf} if csrf else {},
        content_type="application/json",
        body=json.dumps(body).encode(),
    )


def test_purchase_invalid_account_returns_401(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    request = authed_request(
        "/api/purchase",
        "POST",
        accounts={"other@x.com": {"cookies": {}}},
        content_type="application/json",
        body=json.dumps({"account_id": "missing@x.com"}).encode(),
    )
    resp = run_endpoint("/api/purchase", request)
    assert resp.status_code == 401
    assert json.loads(bytes(resp.body)) == {"status": "error", "message": "Auth failed"}


def test_purchase_access_key_none_returns_400(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(main, "make_3hk_request", lambda **kw: None)
    request = _purchase_request(
        {"account_id": "a@b.com", "subscriptionId": "s", "items": [], "price": 0}
    )
    resp = run_endpoint("/api/purchase", request)
    assert resp.status_code == 400
    assert json.loads(bytes(resp.body)) == {"status": "error", "message": "Request failed"}


def test_purchase_normal_flow_payload_and_success(monkeypatch: MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_make(**kw):
        captured.append({"url": kw.get("url"), "method": kw.get("method"), "json": kw.get("json_data")})
        if "purchase/createPurchase" in (kw.get("url") or ""):
            return FakeResponse(200, {"paymentUrl": "https://pay/x"})
        return FakeResponse(200, {"accessPurchaseKey": "KEY"})

    monkeypatch.setattr(main, "make_3hk_request", fake_make)
    monkeypatch.setattr(main, "handle_purchase_event", lambda *a, **k: None)
    invalidated: list[str] = []
    monkeypatch.setattr(main, "delete_cache", lambda k: invalidated.append(k))

    request = _purchase_request(
        {
            "account_id": "a@b.com",
            "subscriptionId": "s",
            "items": [{"offerId": "OFF", "quantity": 2}],
            "price": 100,
            "txnAmount": 30,
        }
    )
    resp = run_endpoint("/api/purchase", request)
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body)) == {"status": "success", "paymentUrl": "https://pay/x"}
    assert invalidated == ["profile_a@b.com"]
    # createPurchase payload shape (SOSIM_VAS normal flow)
    payload = captured[-1]["json"]
    assert payload["purchaseType"] == "SOSIM_VAS"
    assert payload["fUrl"] == "https://simworld.net/SIMworld/main/tc"
    assert payload["accessPurchaseKey"] == "KEY"
    order = payload["order"]
    assert order["channel"] == "ONLINE"
    assert order["autoPayFlag"] is False
    assert order["pmt"]["amnt"] == 70.0  # price 100 - txn 30
    sub = order["orderSubscriptions"][0]
    assert sub["subscriptionId"] == "s"
    assert sub["offers"] == [{"offerId": "OFF", "quantity": 2, "autoRenewFlag": False}]
    assert sub["walletPayment"] == {"txnAmount": 30.0}


def test_purchase_new_line_flow_payload(monkeypatch: MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []

    def fake_make(**kw):
        captured.append({"url": kw.get("url"), "json": kw.get("json_data")})
        if "purchase/createPurchase" in (kw.get("url") or ""):
            return FakeResponse(200, {"paymentUrl": "https://pay/new"})
        return FakeResponse(200, {"accessPurchaseKey": "KEY"})

    monkeypatch.setattr(main, "make_3hk_request", fake_make)
    monkeypatch.setattr(main, "handle_purchase_event", lambda *a, **k: None)
    request = _purchase_request(
        {
            "account_id": "a@b.com",
            "subscriptionId": "s",
            "new_line": True,
            "items": [{"offerId": "VAS1", "quantity": 1}],
            "price": 0,
        }
    )
    resp = run_endpoint("/api/purchase", request)
    assert resp.status_code == 200
    payload = captured[-1]["json"]
    assert payload["purchaseType"] == "PREPAID_DIY"
    assert payload["order"]["channel"] == "GLOBAL_ESIM"
    offers = payload["order"]["orderSubscription"]["offers"]
    # base new-SIM offer prepended
    assert offers[0] == {"offerId": "H3OF00000000001", "quantity": 1, "autoRenewFlag": False}
    assert offers[1] == {"offerId": "VAS1", "quantity": 1, "autoRenewFlag": False}
    assert payload["order"]["orderSubscription"]["simType"] == "ESIM"


def test_purchase_upstream_no_payment_url_returns_400(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "make_3hk_request",
        lambda **kw: FakeResponse(200, {"accessPurchaseKey": "k"}) if "accessPurchaseKey" in (kw.get("url") or "") else FakeResponse(200, {"nope": 1}),
    )
    request = _purchase_request(
        {"account_id": "a@b.com", "subscriptionId": "s", "items": [], "price": 0}
    )
    resp = run_endpoint("/api/purchase", request)
    assert resp.status_code == 400
    assert json.loads(bytes(resp.body)) == {"status": "error", "message": "购买请求失败，请稍后重试"}


# =========================================================================
# /api/sim/transfer contracts (direct invocation)
# =========================================================================


def test_transfer_no_dto_offer_returns_400(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        main, "make_3hk_request", lambda **kw: FakeResponse(200, {"offers": [{"offerSubType": "OTHER"}]})
    )
    request = authed_request(
        "/api/sim/transfer",
        "POST",
        content_type="application/json",
        body=json.dumps({"account_id": "a@b.com", "subscriptionId": "s"}).encode(),
    )
    resp = run_endpoint("/api/sim/transfer", request)
    assert resp.status_code == 400
    assert json.loads(bytes(resp.body)) == {"status": "error", "message": "不支持转移"}


def test_transfer_success_payload_and_cache_invalidation(monkeypatch: MonkeyPatch) -> None:
    captured: list[dict[str, Any]] = []
    invalidated: list[str] = []

    def fake_make(**kw):
        captured.append({"url": kw.get("url"), "json": kw.get("json_data")})
        if "getTransferOffers" in (kw.get("url") or ""):
            return FakeResponse(
                200,
                {
                    "offers": [
                        {
                            "offerSubType": "DTO",
                            "offerId": "DTO1",
                            "products": [
                                {"productId": "PDATA", "productFamily": "DATA"},
                                {"productId": "PVOICE", "productFamily": "VOICE"},
                            ],
                        }
                    ]
                },
            )
        return FakeResponse(200, {})

    monkeypatch.setattr(main, "make_3hk_request", fake_make)
    monkeypatch.setattr(main, "delete_cache", lambda k: invalidated.append(k))
    request = authed_request(
        "/api/sim/transfer",
        "POST",
        content_type="application/json",
        body=json.dumps(
            {
                "account_id": "a@b.com",
                "subscriptionId": "s",
                "sourceMsisdn": "111",
                "targetMsisdn": "222",
                "productFamily": "DATA",
                "balanceResourceId": "9",
                "unit": "MB",
                "amount": "500",
                "userOfferId": "UO",
            }
        ).encode(),
    )
    resp = run_endpoint("/api/sim/transfer", request)
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body)) == {"status": "success"}
    assert invalidated == ["profile_a@b.com"]
    payload = captured[-1]["json"]
    # the deliberate typo "tranferOrder" is part of the contract
    assert "tranferOrder" in payload
    order_sub = payload["tranferOrder"]["orderSubscription"]
    assert order_sub["msisdn"] == "111"
    assert order_sub["volumeUpMsisdn"] == "222"
    offer = order_sub["offers"][0]
    assert offer["offerId"] == "DTO1"
    assert offer["transferOfferId"] == "UO"
    assert offer["offerProduct"]["balanceResourceId"] == 9
    assert offer["offerProduct"]["productId"] == "PDATA"
    assert offer["offerProduct"]["productData"] == {"unit": "MB", "volume": 500.0}


def test_transfer_upstream_non_200_returns_400(monkeypatch: MonkeyPatch) -> None:
    def fake_make(**kw):
        if "getTransferOffers" in (kw.get("url") or ""):
            return FakeResponse(200, {"offers": [{"offerSubType": "DTO", "offerId": "D", "products": [{"productId": "P", "productFamily": "DATA"}]}]})
        return FakeResponse(500)

    monkeypatch.setattr(main, "make_3hk_request", fake_make)
    request = authed_request(
        "/api/sim/transfer",
        "POST",
        content_type="application/json",
        body=json.dumps({"account_id": "a@b.com", "subscriptionId": "s", "productFamily": "DATA", "balanceResourceId": 1, "amount": 1, "unit": "MB", "sourceMsisdn": "1", "targetMsisdn": "2", "userOfferId": "u"}).encode(),
    )
    resp = run_endpoint("/api/sim/transfer", request)
    assert resp.status_code == 400
    assert json.loads(bytes(resp.body)) == {"status": "error", "message": "资源转移请求失败，请稍后重试"}


# =========================================================================
# /api/cmn/check & /api/cmn/numbers contracts (direct invocation)
# =========================================================================


def test_cmn_check_no_offers_returns_400(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(main, "make_3hk_request", lambda **kw: FakeResponse(200, {"offers": []}))
    request = authed_request("/api/cmn/check", "GET")
    request.scope["query_string"] = b"account_id=a@b.com&subscriptionId=s"
    resp = run_endpoint("/api/cmn/check", request)
    assert resp.status_code == 400
    assert json.loads(bytes(resp.body)) == {"status": "error", "message": "无资格"}


def test_cmn_check_returns_first_offer(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(
        main,
        "make_3hk_request",
        lambda **kw: FakeResponse(
            200,
            {"offers": [{"offerId": "C1", "offerSubType": "CMN", "offerPrice": 88, "offerNameChi": "換號"}]},
        ),
    )
    request = authed_request("/api/cmn/check", "GET")
    request.scope["query_string"] = b"account_id=a@b.com&subscriptionId=s"
    resp = run_endpoint("/api/cmn/check", request)
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body)) == {
        "status": "success",
        "data": {"offerId": "C1", "offerSubType": "CMN", "price": 88, "name": "換號"},
    }


def test_cmn_numbers_get_returns_sorted_unique(monkeypatch: MonkeyPatch) -> None:
    captured: list[str] = []
    monkeypatch.setattr(main, "make_3hk_request", lambda **kw: (captured.append(kw.get("method", "")), FakeResponse(200, {"lineList": ["333", "111", "111", "222"]}))[1])
    request = authed_request("/api/cmn/numbers", "GET")
    request.scope["query_string"] = b"account_id=a@b.com&subscriptionId=s"
    resp = run_endpoint("/api/cmn/numbers", request)
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body)) == {"status": "success", "numbers": ["111", "222", "333"]}
    assert captured == ["POST"]  # always POST upstream even on GET


def test_cmn_numbers_fetch_fail_returns_400(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(main, "make_3hk_request", lambda **kw: None)
    request = authed_request("/api/cmn/numbers", "GET")
    request.scope["query_string"] = b"account_id=a@b.com&subscriptionId=s"
    resp = run_endpoint("/api/cmn/numbers", request)
    assert resp.status_code == 400
    assert json.loads(bytes(resp.body)) == {"status": "error", "message": "Fetch failed"}


def test_cmn_numbers_post_without_csrf_returns_403(monkeypatch: MonkeyPatch) -> None:
    request = authed_request(
        "/api/cmn/numbers",
        "POST",
        csrf=None,
        content_type="application/x-www-form-urlencoded",
        body=b"account_id=a@b.com&subscriptionId=s",
    )
    resp = run_endpoint("/api/cmn/numbers", request)
    assert resp.status_code == 403
    assert json.loads(bytes(resp.body)) == {"status": "error", "message": "CSRF token invalid"}


# =========================================================================
# /api/inbox & /api/history contracts (direct invocation)
# =========================================================================


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
    assert ids == [2, 3, 1]  # deduped, sorted by post_dt desc


def test_history_upstream_non_200_returns_400_bare_error(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(main, "make_3hk_request", lambda **kw: FakeResponse(500))
    request = authed_request("/api/history", "GET")
    request.scope["query_string"] = b"account_id=a@b.com&subscriptionId=s"
    resp = run_endpoint("/api/history", request)
    assert resp.status_code == 400
    # bare error shape: no "message" key
    assert json.loads(bytes(resp.body)) == {"status": "error"}


def test_history_success_wraps_upstream_json(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setattr(main, "make_3hk_request", lambda **kw: FakeResponse(200, {"txns": [1, 2]}))
    request = authed_request("/api/history", "GET")
    request.scope["query_string"] = b"account_id=a@b.com&subscriptionId=s"
    resp = run_endpoint("/api/history", request)
    assert resp.status_code == 200
    assert json.loads(bytes(resp.body)) == {"status": "success", "data": {"txns": [1, 2]}}


# =========================================================================
# /api/plans contracts (direct invocation)
# =========================================================================


def test_plans_invalid_account_returns_401_bare_error(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    request = authed_request("/api/plans", "GET", accounts={"other@x.com": {"cookies": {}}})
    request.scope["query_string"] = b"account_id=missing@x.com"
    resp = run_endpoint("/api/plans", request)
    assert resp.status_code == 401
    assert json.loads(bytes(resp.body)) == {"status": "error"}


def test_plans_serves_cached_brand_file(monkeypatch: MonkeyPatch) -> None:
    # plans_cache files exist on disk for THREE; background thread is started but harmless here.
    monkeypatch.setattr(main, "fetch_and_save_plans_background", lambda *a, **k: None)
    request = authed_request("/api/plans", "GET")
    request.scope["query_string"] = b"account_id=a@b.com&subscriptionId=s&brand=THREE"
    resp = run_endpoint("/api/plans", request)
    assert resp.status_code == 200
    body = json.loads(bytes(resp.body))
    assert body["status"] == "success"
    assert "plans" in body


# =========================================================================
# /logout contracts (ASGI driver)
# =========================================================================


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


# =========================================================================
# /internal/session-cleanup contracts (ASGI driver)
# =========================================================================


def test_session_cleanup_wrong_secret_returns_401(monkeypatch: MonkeyPatch) -> None:
    _install_fake_store(monkeypatch)
    resp = invoke("/internal/session-cleanup", method="POST", headers={"x-session-secret": "wrong"})
    assert resp.status == 401
    assert resp.json == {"status": "error", "message": "Unauthorized"}


# =========================================================================
# health/readiness contracts (ASGI driver)
# =========================================================================


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
