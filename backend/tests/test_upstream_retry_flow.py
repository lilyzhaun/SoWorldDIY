"""Upstream contract tests.

These tests preserve the app.main monkeypatch seams and response contracts.
"""

from __future__ import annotations

from typing import Any

import requests
from pytest import MonkeyPatch
from requests.structures import CaseInsensitiveDict
from starlette.datastructures import State

from app.session_store import SessionContext


def test_make_3hk_request_401_triggers_silent_relogin_then_retries(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    calls: list[dict[str, Any]] = []

    class FakeSession:
        def __init__(self) -> None:
            self.cookies = requests.utils.cookiejar_from_dict({})

        def __enter__(self) -> FakeSession:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def request(self, method, url, **kwargs):
            calls.append(
                {"url": url, "is_retry": kwargs.get("json", {}).get("__retry")}
            )
            # First call returns 401, subsequent calls return 200.
            if len(calls) == 1:
                return FakeResponse(401, {})
            return FakeResponse(200, {"ok": True})

    monkeypatch.setattr(main, "get_isolated_session", lambda: FakeSession())
    monkeypatch.setattr(main, "resolve_proxies", lambda url, default: default)
    monkeypatch.setattr(main, "attempt_silent_relogin", lambda *a, **k: True)
    monkeypatch.setattr(main, "_save_session", lambda ctx: None)
    # The retry path calls get_account_context to fetch refreshed cookies.
    monkeypatch.setattr(
        main,
        "get_account_context",
        lambda ctx, aid: {"cookies": {"refreshed": "1"}},
    )

    ctx = _ctx_with_accounts(
        {
            "a@b.com": {
                "cookies": {},
                "login_type": "password",
                "stored_password_encrypted": "x",
            }
        }
    )
    acct = ctx.data["accounts"]["a@b.com"]
    result = main.make_3hk_request(
        request=_make_request("POST", ua="UA"),
        ctx=ctx,
        method="POST",
        url="https://simworld.net/api",
        json_data={"foo": "bar"},
        account_id="a@b.com",
        account_context=acct,
    )
    assert isinstance(result, FakeResponse)
    assert result.status_code == 200
    assert result.json() == {"ok": True}
    # Exactly one 401 then one retry.
    assert len(calls) == 2


def test_make_3hk_request_401_relogin_fails_returns_401_response(
    monkeypatch: MonkeyPatch,
) -> None:
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
            return FakeResponse(401, {})

    monkeypatch.setattr(main, "get_isolated_session", lambda: FakeSession())
    monkeypatch.setattr(main, "resolve_proxies", lambda url, default: default)
    monkeypatch.setattr(main, "attempt_silent_relogin", lambda *a, **k: False)

    ctx = _ctx_with_accounts({"a@b.com": {"cookies": {}}})
    result = main.make_3hk_request(
        request=_make_request("GET", ua="UA"),
        ctx=ctx,
        method="GET",
        url="https://simworld.net/api",
        account_id="a@b.com",
        account_context={"cookies": {}},
    )
    assert isinstance(result, FakeResponse)
    assert result.status_code == 401


def test_make_3hk_request_does_not_retry_after_relogin_already_retried(
    monkeypatch: MonkeyPatch,
) -> None:
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
            return FakeResponse(401, {})

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
        _is_retry=True,
    )
    assert isinstance(result, FakeResponse)
    assert result.status_code == 401


def test_make_3hk_request_401_infers_account_id_from_account_context_identity(
    monkeypatch: MonkeyPatch,
) -> None:
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
            return FakeResponse(401, {})

    monkeypatch.setattr(main, "get_isolated_session", lambda: FakeSession())
    monkeypatch.setattr(main, "resolve_proxies", lambda url, default: default)

    seen: list[str] = []
    monkeypatch.setattr(
        main,
        "attempt_silent_relogin",
        lambda req, ctx, aid, acct: seen.append(aid) or False,
    )

    acct = {"cookies": {}}
    ctx = _ctx_with_accounts({"user@x.com": acct})
    main.make_3hk_request(
        request=_make_request("GET", ua="UA"),
        ctx=ctx,
        method="GET",
        url="https://simworld.net/api",
        account_id=None,
        account_context=acct,
    )
    assert seen == ["user@x.com"]


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
    return type("_Req", (), {"headers": headers, "state": State()})()
