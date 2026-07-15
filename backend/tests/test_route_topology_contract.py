"""Route registration contract tests.

Locks topology/order/methods/names, OpenAPI paths, middleware, mounts,
app identity, and main-module seams that tests monkeypatch against.
"""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any

import anyio
from fastapi.routing import APIRoute
from starlette.routing import Mount

from app import main
from app.main import application, create_app

EXPECTED_API_ROUTES: list[tuple[str, list[str], str]] = [
    ("/_health", ["GET"], "healthcheck"),
    ("/_ready", ["GET"], "readiness"),
    ("/manifest.json", ["GET"], "manifest"),
    ("/sw.js", ["GET"], "service_worker"),
    ("/favicon.ico", ["GET"], "favicon"),
    ("/", ["GET"], "index"),
    ("/api/check-user", ["POST"], "check_user"),
    ("/api/send-otp", ["POST"], "send_otp"),
    ("/login", ["POST"], "handle_login"),
    ("/main", ["GET"], "main_page_default"),
    ("/main/{account_id}", ["GET"], "main_page"),
    ("/api/profile", ["GET"], "get_profile_api"),
    ("/api/plans", ["GET"], "get_plans_api"),
    ("/api/balance", ["GET"], "get_balance"),
    ("/api/purchase", ["POST"], "purchase_plan"),
    ("/api/cmn/check", ["GET"], "check_cmn"),
    ("/api/cmn/numbers", ["POST"], "post_cmn_numbers"),
    ("/api/cmn/purchase", ["POST"], "purchase_cmn"),
    ("/api/sim/transfer", ["POST"], "transfer_resource"),
    ("/api/inbox", ["GET"], "get_inbox"),
    ("/api/history", ["GET"], "get_transaction_history"),
    ("/logout", ["POST"], "logout"),
    ("/internal/session-cleanup", ["POST"], "session_cleanup"),
]

EXPECTED_OPENAPI_PATHS = sorted({path for path, _, _ in EXPECTED_API_ROUTES})

MAIN_SEAMS = [
    "session_store",
    "decrypt_password",
    "get_isolated_session",
    "_save_session",
    "resolve_proxies",
    "attempt_silent_relogin",
    "get_account_context",
    "make_3hk_request",
    "get_cache",
    "set_cache",
    "delete_cache",
    "notify",
    "plans_refreshing",
    "verify_auth_code",
    "encrypt_password",
    "_require_login",
    "_clear_session",
    "_create_session",
    "_validate_csrf",
    "_mark_session_cookie_for_deletion",
    "get_brand_by_sub_id",
    "fetch_and_save_plans_background",
    "handle_purchase_event",
    "_json_error",
    "_json_success",
    "_redirect_to_login",
    "_upstream_error",
    "internal_logout_account",
    "lifespan",
    "create_app",
    "application",
    "app",
    "SessionMiddleware",
    "BASE_HEADERS",
    "PROXIES",
    "SUB_BRANDS",
    "redis_client",
    "SESSION_SECRET",
    "FRONTEND_DIST_DIR",
    "FRONTEND_STATIC_DIR",
    "PLANS_CACHE_DIR",
    "auth_code_store",
    "_MainDeps",
]


def _api_routes() -> list[APIRoute]:
    return [route for route in main.app.routes if isinstance(route, APIRoute)]


def test_api_route_topology_order_methods_and_names() -> None:
    observed = [
        (
            route.path,
            sorted(m for m in route.methods if m not in {"HEAD", "OPTIONS"}),
            route.name,
        )
        for route in _api_routes()
    ]
    assert observed == EXPECTED_API_ROUTES
    for route, (_, _, expected_name) in zip(
        _api_routes(), EXPECTED_API_ROUTES, strict=True
    ):
        assert route.endpoint.__name__ == expected_name


def test_openapi_paths_match_registered_api_routes() -> None:
    paths = sorted(main.app.openapi()["paths"].keys())
    assert paths == EXPECTED_OPENAPI_PATHS


def test_cmn_numbers_route_is_post_only() -> None:
    cmn_openapi = main.app.openapi()["paths"].get("/api/cmn/numbers", {})
    assert "get" not in cmn_openapi
    assert "post" in cmn_openapi
    assert cmn_openapi["post"]["operationId"] == "post_cmn_numbers"


def test_middleware_includes_session_middleware() -> None:
    middleware_types = []
    for item in main.app.user_middleware:
        cls = getattr(item, "cls", None)
        if cls is not None:
            middleware_types.append(cls.__name__)
        else:
            middleware_types.append(type(item).__name__)
    assert "SessionMiddleware" in middleware_types


def test_static_mounts_present() -> None:
    mounts = {
        route.path: route.name for route in main.app.routes if isinstance(route, Mount)
    }
    if main.FRONTEND_DIST_DIR.exists():
        assert mounts.get("/assets") == "assets"
    else:
        assert mounts.get("/assets") is None
    if main.FRONTEND_STATIC_DIR.exists():
        assert mounts.get("/static") == "static"
    else:
        assert mounts.get("/static") is None


def test_static_mounts_present_on_fresh_app_with_created_frontend_dirs(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    dist = tmp_path / "frontend-dist"
    static_dir = dist / "static"
    assets_dir = dist / "assets"
    dist.mkdir()
    static_dir.mkdir(parents=True)
    assets_dir.mkdir()

    monkeypatch.setattr(main, "FRONTEND_DIST_DIR", dist)
    monkeypatch.setattr(main, "FRONTEND_STATIC_DIR", static_dir)

    fresh = create_app()
    mounts = {
        route.path: route.name for route in fresh.routes if isinstance(route, Mount)
    }
    assert mounts.get("/assets") == "assets"
    assert mounts.get("/static") == "static"


def test_create_app_skips_assets_mount_when_missing_frontend_dist(
    monkeypatch: Any,
    tmp_path: Path,
) -> None:
    dist = tmp_path / "missing-dist"
    plans_cache = tmp_path / "plans-cache"
    plans_cache.mkdir()

    monkeypatch.setattr(main, "FRONTEND_DIST_DIR", dist)
    monkeypatch.setattr(main, "FRONTEND_STATIC_DIR", dist / "static")
    monkeypatch.setattr(main, "PLANS_CACHE_DIR", plans_cache)

    class FakeRedis:
        def ping(self) -> bool:
            return True

    monkeypatch.setattr(main, "redis_client", FakeRedis())

    fresh = create_app()
    mounts = {
        route.path: route.name for route in fresh.routes if isinstance(route, Mount)
    }
    assert "/assets" not in mounts
    assert mounts.get("/static") is None

    endpoint: Callable[..., Any] | None = None
    for route in fresh.routes:
        if isinstance(route, APIRoute) and route.path == "/_ready":
            endpoint = route.endpoint
            break
    assert endpoint is not None

    response = anyio.run(endpoint)
    assert response.status_code == 503
    payload = json.loads(response.body)
    assert payload["status"] == "error"
    assert payload["checks"]["frontend_assets"] is False
    assert payload["checks"]["frontend_index"] is False


def test_app_identity_and_create_app_factory() -> None:
    assert main.app is application
    assert main.app is main.application
    assert main.app.title == "3HK New Native FastAPI App"
    assert main.app.version == "1.0.0"
    assert callable(create_app)
    fresh = create_app()
    assert fresh is not main.app
    fresh_paths = [route.path for route in fresh.routes if isinstance(route, APIRoute)]
    assert fresh_paths == [path for path, _, _ in EXPECTED_API_ROUTES]


def test_main_module_seams_remain_importable() -> None:
    for name in MAIN_SEAMS:
        assert hasattr(main, name), f"missing main seam: {name}"


def test_route_handlers_see_monkeypatched_main_seams(monkeypatch: Any) -> None:
    """Handlers must resolve deps at request time, not capture callables at import."""
    from starlette.requests import Request

    marker = object()

    def fake_require_login(_request: Request) -> None:
        _ = marker
        return None

    monkeypatch.setattr(main, "_require_login", fake_require_login)

    endpoint: Callable[..., Any] | None = None
    for route in _api_routes():
        if route.path == "/api/balance":
            endpoint = route.endpoint
            break
    assert endpoint is not None

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/balance",
            "headers": [],
            "query_string": b"",
        }
    )
    # If the handler closed over the pre-patch symbol, this would not redirect.
    import anyio
    from starlette.responses import Response

    response = anyio.run(endpoint, request)
    assert isinstance(response, Response)
    assert response.status_code == 302
