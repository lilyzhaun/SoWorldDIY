"""Shared fakes and helpers for backend route contract tests.

Used by the domain-split contract modules under tests/test_contract_*.py.
No production behavior is changed by these helpers.
"""

from __future__ import annotations

import json
from collections.abc import Callable, Sequence
from typing import Any

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

    def __enter__(self) -> FakeIsolatedSession:
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


def _purchase_request(body: dict[str, Any], csrf: str | None = "tok") -> Request:
    return authed_request(
        "/api/purchase",
        "POST",
        headers={CSRF_HEADER_NAME: csrf} if csrf else {},
        content_type="application/json",
        body=json.dumps(body).encode(),
    )

