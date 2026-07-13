"""Contract tests: /api/profile."""

from __future__ import annotations

import json
from typing import Any

from pytest import MonkeyPatch

from app import main
from tests.contract_helpers import (
    FakeResponse,
    _install_fake_store,
    _profile_upstream,
    authed_request,
    run_endpoint,
)


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

