"""Upstream contract tests.

These tests preserve the app.main monkeypatch seams and response contracts.
"""

from __future__ import annotations

from typing import Any

import requests
from pytest import MonkeyPatch

from app.session_store import SessionContext

# ===== attempt_silent_relogin contracts =====


def test_attempt_silent_relogin_skips_otp_accounts(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    ctx = _ctx_with_accounts({"a@b.com": {"login_type": "otp"}})
    assert (
        main.attempt_silent_relogin(
            object(), ctx, "a@b.com", ctx.data["accounts"]["a@b.com"]
        )
        is False
    )


def test_attempt_silent_relogin_skips_when_no_stored_password(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main

    ctx = _ctx_with_accounts({"a@b.com": {"login_type": "password"}})
    assert (
        main.attempt_silent_relogin(
            object(), ctx, "a@b.com", ctx.data["accounts"]["a@b.com"]
        )
        is False
    )


def test_attempt_silent_relogin_success_updates_cookies(
    monkeypatch: MonkeyPatch,
) -> None:
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

        def __enter__(self) -> FakeSession:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def post(self, url, json, headers, proxies, timeout):
            return FakeResponse(204, cookies={"sess": "new"})

    monkeypatch.setattr(main, "get_isolated_session", lambda: FakeSession())

    ctx = _ctx_with_accounts(
        {
            "a@b.com": {
                "login_type": "password",
                "stored_password_encrypted": "enc",
                "sub_brand": "SOSIM",
            }
        }
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

        def __enter__(self) -> FakeSession:
            return self

        def __exit__(self, *_: object) -> None:
            pass

        def post(self, url, json, headers, proxies, timeout):
            return FakeResponse(401, {})

    monkeypatch.setattr(main, "get_isolated_session", lambda: FakeSession())
    ctx = _ctx_with_accounts(
        {"a@b.com": {"login_type": "password", "stored_password_encrypted": "enc"}}
    )
    ok = main.attempt_silent_relogin(
        _make_request("POST", ua="UA"), ctx, "a@b.com", ctx.data["accounts"]["a@b.com"]
    )
    assert ok is False


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
