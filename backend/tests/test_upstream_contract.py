"""Upstream-request and helper contract tests.

Locks behavior of make_3hk_request (401 silent-relogin retry, cookie propagation,
None-on-failure), attempt_silent_relogin, get_brand_by_sub_id, get_account_context,
internal_logout_account, and the public error/success response shapes.

All patches target names in the app.main module namespace so they survive
future refactors as long as those names remain importable from app.main.
"""

from __future__ import annotations

import json as _json
from typing import Any

import requests
from pytest import MonkeyPatch

from app.main import (
    _json_error,
    _json_success,
    _redirect_to_login,
    _upstream_error,
    get_account_context,
)
from app.session_store import SessionContext

# ----- helpers shared with test_app_contracts.py (duplicated intentionally
#       so this file is self-contained and not coupled to the other). ----


def _ctx_with_accounts(accounts: dict[str, Any]) -> SessionContext:
    return SessionContext(sid="sid-test", data={"accounts": accounts, "csrf_token": "tok"})


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

        def __enter__(self) -> "FakeSession":
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


def test_make_3hk_request_401_triggers_silent_relogin_then_retries(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    calls: list[dict[str, Any]] = []

    class FakeSession:
        def __init__(self) -> None:
            self.cookies = requests.utils.cookiejar_from_dict({})

        def __enter__(self) -> "FakeSession":
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def request(self, method, url, **kwargs):
            calls.append({"url": url, "is_retry": kwargs.get("json", {}).get("__retry")})
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
        {"a@b.com": {"cookies": {}, "login_type": "password", "stored_password_encrypted": "x"}}
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

        def __enter__(self) -> "FakeSession":
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

        def __enter__(self) -> "FakeSession":
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


def test_make_3hk_request_exception_returns_none(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    class FakeSession:
        def __init__(self) -> None:
            self.cookies = requests.utils.cookiejar_from_dict({})

        def __enter__(self) -> "FakeSession":
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


def test_make_3hk_request_401_infers_account_id_from_account_context_identity(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    class FakeSession:
        def __init__(self) -> None:
            self.cookies = requests.utils.cookiejar_from_dict({})

        def __enter__(self) -> "FakeSession":
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


# ===== attempt_silent_relogin contracts =====


def test_attempt_silent_relogin_skips_otp_accounts(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    ctx = _ctx_with_accounts({"a@b.com": {"login_type": "otp"}})
    assert main.attempt_silent_relogin(object(), ctx, "a@b.com", ctx.data["accounts"]["a@b.com"]) is False


def test_attempt_silent_relogin_skips_when_no_stored_password(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    ctx = _ctx_with_accounts({"a@b.com": {"login_type": "password"}})
    assert main.attempt_silent_relogin(object(), ctx, "a@b.com", ctx.data["accounts"]["a@b.com"]) is False


def test_attempt_silent_relogin_success_updates_cookies(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    monkeypatch.setattr(
        main, "decrypt_password", lambda enc: "plain-pw" if enc == "enc" else None
    )
    saved: list[SessionContext] = []
    monkeypatch.setattr(main, "_save_session", lambda c: saved.append(c))

    class FakeSession:
        def __init__(self) -> None:
            self.cookies = requests.utils.cookiejar_from_dict({"sess": "new"})

        def __enter__(self) -> "FakeSession":
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def post(self, url, json, headers, proxies, timeout):
            return FakeResponse(204, cookies={"sess": "new"})

    monkeypatch.setattr(main, "get_isolated_session", lambda: FakeSession())

    ctx = _ctx_with_accounts(
        {"a@b.com": {"login_type": "password", "stored_password_encrypted": "enc", "sub_brand": "SOSIM"}}
    )
    ok = main.attempt_silent_relogin(
        _make_request("POST", ua="UA"), ctx, "a@b.com", ctx.data["accounts"]["a@b.com"]
    )
    assert ok is True
    assert ctx.data["accounts"]["a@b.com"]["cookies"] == {"sess": "new"}
    assert saved == [ctx]


def test_attempt_silent_relogin_non_204_returns_false(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    monkeypatch.setattr(main, "decrypt_password", lambda enc: "pw")
    monkeypatch.setattr(main, "_save_session", lambda ctx: None)

    class FakeSession:
        def __init__(self) -> None:
            self.cookies = requests.utils.cookiejar_from_dict({})

        def __enter__(self) -> "FakeSession":
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def post(self, url, json, headers, proxies, timeout):
            return FakeResponse(401, {})

    monkeypatch.setattr(main, "get_isolated_session", lambda: FakeSession())
    ctx = _ctx_with_accounts({"a@b.com": {"login_type": "password", "stored_password_encrypted": "enc"}})
    ok = main.attempt_silent_relogin(
        _make_request("POST", ua="UA"), ctx, "a@b.com", ctx.data["accounts"]["a@b.com"]
    )
    assert ok is False


# ===== get_brand_by_sub_id contracts =====


def test_brand_by_sub_id_uses_cached_profile_subscription(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    monkeypatch.setattr(
        main,
        "get_cache",
        lambda key: {
            "data": {
                "subscriptions": [
                    {"subscriptionId": "sub-1", "brand": "SOSIM"},
                    {"subscriptionId": "sub-2", "brand": "HAHA"},
                ]
            }
        }
        if key == "profile_acct"
        else None,
    )
    ctx = _ctx_with_accounts({"acct": {"sub_brand": "THREE"}})
    assert main.get_brand_by_sub_id(ctx, "sub-2", "acct") == "HAHA"


def test_brand_by_sub_id_falls_back_to_account_sub_brand(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    monkeypatch.setattr(main, "get_cache", lambda key: None)
    ctx = _ctx_with_accounts({"acct": {"sub_brand": "TRADER"}})
    assert main.get_brand_by_sub_id(ctx, "sub-9", "acct") == "TRADER"


def test_brand_by_sub_id_defaults_to_three_when_no_account(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    monkeypatch.setattr(main, "get_cache", lambda key: None)
    ctx = _ctx_with_accounts({})
    assert main.get_brand_by_sub_id(ctx, "sub-1", None) == "THREE"


# ===== get_account_context contracts =====


def test_get_account_context_returns_none_for_missing_id() -> None:
    ctx = _ctx_with_accounts({"a@b.com": {"cookies": {}}})
    assert get_account_context(ctx, None) is None
    assert get_account_context(ctx, "missing@x.com") is None


def test_get_account_context_returns_account_for_known_id() -> None:
    acct = {"cookies": {"k": "v"}, "sub_brand": "SOSIM"}
    ctx = _ctx_with_accounts({"a@b.com": acct})
    assert get_account_context(ctx, "a@b.com") is acct


# ===== internal_logout_account contracts =====


def test_internal_logout_account_clears_session_when_last_account(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    cleared: list[str] = []
    monkeypatch.setattr(main, "delete_cache", lambda key: cleared.append(key))
    monkeypatch.setattr(main, "_clear_session", lambda ctx: ctx.data.clear())

    ctx = _ctx_with_accounts({"a@b.com": {"cookies": {}}})
    has_left = main.internal_logout_account(ctx, "a@b.com")
    assert has_left is False
    assert ctx.data == {}
    assert cleared == ["profile_a@b.com"]


def test_internal_logout_account_keeps_session_with_remaining(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    cleared: list[str] = []
    monkeypatch.setattr(main, "delete_cache", lambda key: cleared.append(key))
    saved: list[SessionContext] = []
    monkeypatch.setattr(main, "_save_session", lambda ctx: saved.append(ctx))

    ctx = _ctx_with_accounts({"a@b.com": {"cookies": {}}, "c@d.com": {"cookies": {}}})
    has_left = main.internal_logout_account(ctx, "a@b.com")
    assert has_left is True
    assert "a@b.com" not in ctx.data["accounts"]
    assert "c@d.com" in ctx.data["accounts"]
    assert saved == [ctx]


def test_internal_logout_account_unknown_id_is_noop(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    monkeypatch.setattr(main, "delete_cache", lambda key: None)
    monkeypatch.setattr(main, "_save_session", lambda ctx: None)
    ctx = _ctx_with_accounts({"a@b.com": {"cookies": {}}})
    has_left = main.internal_logout_account(ctx, "unknown@x.com")
    assert has_left is True
    assert "a@b.com" in ctx.data["accounts"]


# ===== response shape contracts =====


def test_json_error_shape() -> None:
    resp = _json_error("boom", 418)
    assert resp.status_code == 418
    assert _json.loads(bytes(resp.body)) == {"status": "error", "message": "boom"}


def test_json_success_shape() -> None:
    resp = _json_success({"status": "success", "x": 1})
    assert resp.status_code == 200
    assert _json.loads(bytes(resp.body)) == {"status": "success", "x": 1}


def test_upstream_error_with_none_response(monkeypatch: MonkeyPatch) -> None:
    resp = _upstream_error(None, public_message="custom", status_code=400)
    assert resp.status_code == 400
    assert _json.loads(bytes(resp.body)) == {"status": "error", "message": "custom"}


def test_upstream_error_with_response(monkeypatch: MonkeyPatch) -> None:
    resp = _upstream_error(FakeResponse(500, text="srv-err"), public_message="pub", status_code=400)
    assert resp.status_code == 400
    assert _json.loads(bytes(resp.body)) == {"status": "error", "message": "pub"}


def test_redirect_to_login_shape() -> None:
    resp = _redirect_to_login()
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


# ----- internal: build a minimal Request-like object ----


def _make_request(method: str, ua: str = "Mozilla/5.0"):
    """Build a lightweight stand-in for starlette Request.

    Only the attributes make_3hk_request / attempt_silent_relogin read are populated:
    headers.get('User-Agent', ...).
    """

    class _Headers:
        def get(self, name: str, default: str = "") -> str:
            if name.lower() == "user-agent":
                return ua
            return default

    class _Req:
        headers = _Headers()

    return _Req()