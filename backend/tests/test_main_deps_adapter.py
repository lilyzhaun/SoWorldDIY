"""Focused tests for the module-backed MainDepsAdapter late-binding contract."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
from typing import Any, cast

from fastapi.routing import APIRoute
from starlette.requests import Request
from starlette.responses import Response

from app import main
from app.main import create_app
from app.main_deps import MainDepsAdapter, MainModuleSource


class _MutableSource:
    def __init__(self, **values: object) -> None:
        for key, value in values.items():
            setattr(self, key, value)


def _as_main_source(module: object) -> MainModuleSource:
    return cast(MainModuleSource, module)


def _make_source(**overrides: object) -> MainModuleSource:
    base: dict[str, object] = {
        "session_store": object(),
        "decrypt_password": lambda x: x,
        "get_isolated_session": lambda: None,
        "_save_session": lambda ctx: None,
        "resolve_proxies": lambda url, default: default,
        "attempt_silent_relogin": lambda *a, **k: False,
        "get_account_context": lambda *a, **k: None,
        "make_3hk_request": lambda **k: None,
        "get_cache": lambda k: None,
        "set_cache": lambda *a, **k: None,
        "delete_cache": lambda k: None,
        "plans_refreshing": set(),
        "verify_auth_code": lambda code, consume: (True, "ok"),
        "_json_success": lambda data: None,
        "_json_error": lambda msg, status: None,
        "_upstream_error": lambda *a, **k: None,
        "_create_session": lambda: None,
        "encrypt_password": lambda x: x,
        "_require_login": lambda request: None,
        "get_brand_by_sub_id": lambda *a, **k: "THREE",
        "fetch_and_save_plans_background": lambda *a, **k: None,
        "_redirect_to_login": lambda: None,
        "_validate_csrf": lambda request, ctx: None,
        "internal_logout_account": lambda ctx, account_id: False,
        "_mark_session_cookie_for_deletion": lambda request: None,
        "_clear_session": lambda ctx: None,
        "BASE_HEADERS": {"Host": "initial.example"},
        "PROXIES": None,
        "SUB_BRANDS": ["THREE"],
        "FRONTEND_DIST_DIR": Path("/tmp/dist"),
        "PLANS_CACHE_DIR": Path("/tmp/plans"),
        "SESSION_SECRET": "initial-secret",
        "redis_client": object(),
    }
    base.update(overrides)
    return _as_main_source(_MutableSource(**base))


def test_adapter_reassigns_callable_after_construction() -> None:
    """Callable seams must re-read source after adapter construction."""
    source = _make_source()
    adapter = MainDepsAdapter(source=source)
    raw = cast(Any, source)

    calls: list[str] = []

    def original() -> None:
        calls.append("original")

    def patched() -> None:
        calls.append("patched")

    raw.get_isolated_session = original
    assert adapter.get_isolated_session is original
    _ = adapter.get_isolated_session()
    assert calls == ["original"]

    raw.get_isolated_session = patched
    assert adapter.get_isolated_session is patched
    _ = adapter.get_isolated_session()
    assert calls == ["original", "patched"]


def test_adapter_reassigns_constant_after_construction() -> None:
    """Constant seams must re-read source values without caching."""
    source = _make_source(SESSION_SECRET="before", SUB_BRANDS=["A"])
    adapter = MainDepsAdapter(source=source)
    raw = cast(Any, source)

    assert adapter.SESSION_SECRET == "before"
    assert list(adapter.SUB_BRANDS) == ["A"]
    assert adapter.BASE_HEADERS["Host"] == "initial.example"

    raw.SESSION_SECRET = "after"
    raw.SUB_BRANDS = ["B", "C"]
    raw.BASE_HEADERS = {"Host": "live.example"}

    assert adapter.SESSION_SECRET == "after"
    assert list(adapter.SUB_BRANDS) == ["B", "C"]
    assert adapter.BASE_HEADERS["Host"] == "live.example"


def test_adapter_reassigns_session_store_after_construction() -> None:
    """session_store must be late-bound through the adapter."""
    first = object()
    second = object()
    source = _make_source(session_store=first)
    adapter = MainDepsAdapter(source=source)
    raw = cast(Any, source)

    assert adapter.session_store is first
    raw.session_store = second
    assert adapter.session_store is second


def test_main_maindeps_alias_and_live_session_store_use_adapter() -> None:
    """main exposes _MainDeps alias and _live_session_store reads via adapter."""
    assert main._MainDeps is MainDepsAdapter
    assert isinstance(main._main_deps, MainDepsAdapter)
    assert main._live_session_store() is main.session_store


def test_fresh_create_app_handlers_see_later_monkeypatches(monkeypatch: Any) -> None:
    """Handlers registered on a fresh create_app() must see later main patches."""
    import anyio

    fresh = create_app()
    endpoint: Callable[..., Any] | None = None
    for route in fresh.routes:
        if isinstance(route, APIRoute) and route.path == "/api/balance":
            endpoint = route.endpoint
            break
    assert endpoint is not None

    def fake_require_login(_request: Request) -> None:
        return None

    # Patch after registration — adapter must not have closed over old callable.
    monkeypatch.setattr(main, "_require_login", fake_require_login)

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/balance",
            "headers": [],
            "query_string": b"",
        }
    )
    response = anyio.run(endpoint, request)
    assert isinstance(response, Response)
    assert response.status_code == 302


def test_fresh_create_app_reads_live_session_secret(monkeypatch: Any) -> None:
    """SESSION_SECRET on a fresh app is late-bound via the shared module adapter."""
    import anyio
    from starlette.requests import Request as StarletteRequest

    fresh = create_app()
    endpoint: Callable[..., Any] | None = None
    for route in fresh.routes:
        if isinstance(route, APIRoute) and route.path == "/internal/session-cleanup":
            endpoint = route.endpoint
            break
    assert endpoint is not None

    monkeypatch.setattr(main, "SESSION_SECRET", "fresh-app-secret")

    class FakeRedis:
        def ping(self) -> bool:
            return True

    monkeypatch.setattr(main, "redis_client", FakeRedis())

    done = {"flag": False}

    async def receive() -> dict[str, object]:
        if done["flag"]:
            return {"type": "http.disconnect"}
        done["flag"] = True
        return {"type": "http.request", "body": b"{}", "more_body": False}

    request = StarletteRequest(
        {
            "type": "http",
            "method": "POST",
            "path": "/internal/session-cleanup",
            "headers": [(b"x-session-secret", b"fresh-app-secret")],
            "query_string": b"",
        },
        receive=receive,
    )
    response = anyio.run(endpoint, request)
    assert response.status_code == 200
