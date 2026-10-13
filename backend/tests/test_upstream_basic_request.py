"""Upstream contract tests.

These tests preserve the app.main monkeypatch seams and response contracts.
"""

from __future__ import annotations

from typing import Any

import requests
from pytest import MonkeyPatch
from requests.structures import CaseInsensitiveDict

from app.session_store import SessionContext

# ===== make_3hk_request contracts =====


def test_make_3hk_request_returns_none_when_account_context_missing(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    ctx = _ctx_with_accounts({"a@b.com": {"cookies": {}}})
    result = main.make_3hk_request(
        request=object(),
        ctx=ctx,
        method="GET",
        url="https://example.com",
        account_id="a@b.com",
        account_context=None,
    )
    assert result is None


def test_make_3hk_request_passes_cookies_and_returns_response(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    captured: dict[str, Any] = {}

    class FakeSession:
        def __init__(self) -> None:
            self.cookies = requests.utils.cookiejar_from_dict({"existing": "c"})

        def __enter__(self) -> FakeSession:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def request(self, method, url, **kwargs):
            captured["method"] = method
            captured["url"] = url
            captured["json"] = kwargs.get("json")
            captured["params"] = kwargs.get("params")
            captured["ua"] = kwargs["headers"].get("User-Agent")
            return FakeResponse(200, {"ok": True}, cookies={"sess": "new"})

    monkeypatch.setattr(main, "get_isolated_session", lambda: FakeSession())
    monkeypatch.setattr(main, "resolve_proxies", lambda url, default: default)
    monkeypatch.setattr(main, "_save_session", lambda ctx: None)

    ctx = _ctx_with_accounts({"a@b.com": {"cookies": {"old": "v"}}})
    acct = {"cookies": {"old": "v"}}
    result = main.make_3hk_request(
        request=_make_request("GET", ua="UA-test"),
        ctx=ctx,
        method="GET",
        url="https://simworld.net/test",
        account_id="a@b.com",
        account_context=acct,
    )
    assert isinstance(result, FakeResponse)
    assert result.status_code == 200
    assert captured["method"] == "GET"
    assert captured["url"] == "https://simworld.net/test"
    assert captured["ua"] == "UA-test"
    # response cookies merged into account_context.cookies
    assert acct["cookies"] == {"old": "v", "sess": "new"}
    # persisted into session accounts map
    assert ctx.data["accounts"]["a@b.com"]["cookies"] == {"old": "v", "sess": "new"}


def test_make_3hk_request_exception_returns_none(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    class FakeSession:
        def __init__(self) -> None:
            self.cookies = requests.utils.cookiejar_from_dict({})

        def __enter__(self) -> FakeSession:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def request(self, method, url, **kwargs):
            raise ConnectionError("boom")

    monkeypatch.setattr(main, "get_isolated_session", lambda: FakeSession())
    monkeypatch.setattr(main, "resolve_proxies", lambda url, default: default)

    ctx = _ctx_with_accounts({"a@b.com": {"cookies": {}}})
    result = main.make_3hk_request(
        request=_make_request("GET", ua="UA"),
        ctx=ctx,
        method="GET",
        url="https://simworld.net/api",
        account_id="a@b.com",
        account_context={"cookies": {}},
    )
    assert result is None


def test_completed_write_result_survives_session_refresh_conflict(
    monkeypatch: MonkeyPatch,
):
    from app import main
    from app.session_store import SessionConflictError
    from tests.contract_support import build_request

    response = FakeResponse(
        200, {"paymentUrl": "https://pay.example/"}, cookies={"upstream": "new"}
    )

    class Session:
        cookies = requests.utils.cookiejar_from_dict({})

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def request(self, *args, **kwargs):
            return response

    def conflict(ctx):
        raise SessionConflictError("revoked")

    monkeypatch.setattr(main, "get_isolated_session", Session)
    monkeypatch.setattr(main, "_save_session", conflict)
    request = build_request("POST", "/api/purchase")
    account = {"cookies": {}}
    result = main.make_3hk_request(
        request,
        _ctx_with_accounts({"account": account}),
        "POST",
        "https://simworld.net/synthetic",
        account_id="account",
        account_context=account,
    )
    assert result is response
    assert request.state.delete_session_cookie


def _ctx_with_accounts(accounts: dict[str, Any]) -> SessionContext:
    return SessionContext(
        sid="sid-test", data={"accounts": accounts, "csrf_token": "tok"}
    )


class FakeResponse:
    """Mimics requests.Response just enough for the routes."""

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


# ----- internal: build a minimal Request-like object ----


def _make_request(method: str, ua: str = "Mozilla/5.0"):
    headers = CaseInsensitiveDict({"User-Agent": ua})
    return type("_Req", (), {"headers": headers})()
