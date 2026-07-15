"""Upstream contract tests.

These tests preserve the app.main monkeypatch seams and response contracts.
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

# ===== get_brand_by_sub_id contracts =====


def test_brand_by_sub_id_uses_cached_profile_subscription(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    monkeypatch.setattr(
        main,
        "get_cache",
        lambda key: (
            {
                "data": {
                    "subscriptions": [
                        {"subscriptionId": "sub-1", "brand": "SOSIM"},
                        {"subscriptionId": "sub-2", "brand": "HAHA"},
                    ]
                }
            }
            if key == "profile_acct"
            else None
        ),
    )
    ctx = _ctx_with_accounts({"acct": {"sub_brand": "THREE"}})
    assert main.get_brand_by_sub_id(ctx, "sub-2", "acct") == "HAHA"


def test_brand_by_sub_id_falls_back_to_account_sub_brand(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    monkeypatch.setattr(main, "get_cache", lambda key: None)
    ctx = _ctx_with_accounts({"acct": {"sub_brand": "TRADER"}})
    assert main.get_brand_by_sub_id(ctx, "sub-9", "acct") == "TRADER"


def test_brand_by_sub_id_defaults_to_three_when_no_account(
    monkeypatch: MonkeyPatch,
) -> None:
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


def test_internal_logout_account_clears_session_when_last_account(
    monkeypatch: MonkeyPatch,
) -> None:
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


def test_internal_logout_account_keeps_session_with_remaining(
    monkeypatch: MonkeyPatch,
) -> None:
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
    assert _json.loads(bytes(resp.body)) == {
        "status": "error",
        "message": "custom",
        "code": "upstream_error",
    }


def test_upstream_error_with_response(monkeypatch: MonkeyPatch) -> None:
    resp = _upstream_error(
        FakeResponse(500, text="srv-err"), public_message="pub", status_code=400
    )
    assert resp.status_code == 400
    assert _json.loads(bytes(resp.body)) == {
        "status": "error",
        "message": "pub",
        "code": "upstream_error",
    }


def test_redirect_to_login_shape() -> None:
    resp = _redirect_to_login()
    assert resp.status_code == 302
    assert resp.headers["location"] == "/"


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


def _make_request(method: str, ua: str = "Mozilla/5.0"):
    """Build a lightweight stand-in for starlette Request."""

    class _Headers:
        def get(self, name: str, default: str = "") -> str:
            if name.lower() == "user-agent":
                return ua
            return default

    class _Req:
        headers = _Headers()

    return _Req()
