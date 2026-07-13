from __future__ import annotations

import copy
from typing import Any

from app import main
from app.session_utils import scrub_legacy_account_secrets
from tests.contract_support import (
    FakeResponse,
    MonkeyPatch,
    _authed_session,
    _install_fake_store,
    invoke,
)


def test_scrub_legacy_account_secrets_removes_only_secret_keys() -> None:
    session_data: dict[str, Any] = {
        "csrf_token": "tok",
        "accounts": {
            "a@b.com": {
                "cookies": {"sid": "1"},
                "sub_brand": "THREE",
                "login_type": "password",
                "stored_password_encrypted": "enc-value",
                "credential": "plaintext-secret",
                "auth_code": "CODE123",
                "custom_flag": True,
            },
            "b@c.com": {
                "cookies": {},
                "sub_brand": "SOSIM",
                "login_type": "otp",
                "credential": "OTP: 999999",
            },
            "skip-me": "not-a-mapping",
        },
        "unrelated": {"keep": "yes"},
    }

    changed = scrub_legacy_account_secrets(session_data)

    assert changed is True
    first = session_data["accounts"]["a@b.com"]
    assert "credential" not in first
    assert "auth_code" not in first
    assert first["cookies"] == {"sid": "1"}
    assert first["sub_brand"] == "THREE"
    assert first["login_type"] == "password"
    assert first["stored_password_encrypted"] == "enc-value"
    assert first["custom_flag"] is True
    second = session_data["accounts"]["b@c.com"]
    assert "credential" not in second
    assert second["login_type"] == "otp"
    assert session_data["accounts"]["skip-me"] == "not-a-mapping"
    assert session_data["unrelated"] == {"keep": "yes"}
    assert session_data["csrf_token"] == "tok"


def test_scrub_legacy_account_secrets_is_noop_when_clean() -> None:
    session_data: dict[str, Any] = {
        "accounts": {
            "a@b.com": {
                "cookies": {},
                "sub_brand": "THREE",
                "login_type": "password",
                "stored_password_encrypted": "enc",
            }
        }
    }
    assert scrub_legacy_account_secrets(session_data) is False
    assert scrub_legacy_account_secrets({}) is False
    assert scrub_legacy_account_secrets({"accounts": "bad"}) is False


def test_middleware_scrubs_legacy_secrets_and_persists(
    monkeypatch: MonkeyPatch,
) -> None:
    store = _install_fake_store(monkeypatch)
    sid, _csrf = _authed_session(
        store,
        accounts={
            "a@b.com": {
                "cookies": {},
                "sub_brand": "THREE",
                "login_type": "password",
                "stored_password_encrypted": "enc",
                "credential": "legacy-password",
                "auth_code": "LEGACY-CODE",
                "keep_me": "yes",
            }
        },
    )

    # Mimic Redis load: return a detached copy so persistence requires save().
    def load_copy(session_id: str) -> dict[str, Any] | None:
        data = store.sessions.get(session_id)
        return copy.deepcopy(data) if data is not None else None

    monkeypatch.setattr(store, "load", load_copy)
    monkeypatch.setattr(
        main, "make_3hk_request", lambda **kw: FakeResponse(200, [{"amount": 0}])
    )

    resp = invoke(
        "/api/balance?account_id=a@b.com&subscriptionId=s",
        headers={"cookie": f"session={sid}"},
    )
    assert resp.status == 200

    persisted = store.sessions[sid]["accounts"]["a@b.com"]
    assert "credential" not in persisted
    assert "auth_code" not in persisted
    assert persisted["stored_password_encrypted"] == "enc"
    assert persisted["keep_me"] == "yes"
    assert persisted["login_type"] == "password"
    assert persisted["sub_brand"] == "THREE"
