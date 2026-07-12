"""Route registration contract tests.

Locks topology/order/methods/names, OpenAPI paths, middleware, mounts,
app identity, and main-module seams that tests monkeypatch against.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.routing import APIRoute
from starlette.routing import Mount

from app import main
from app.main import application, create_app

EXPECTED_API_ROUTES: list[tuple[str, list[str], str]] = [
    ("/_health", ["GET"], "healthcheck"),
    ("/_ready", ["GET"], "readiness"),
    ("/manifest.json", ["GET"], "manifest"),
    ("/sw.js", ["GET"], "service_worker"),
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
    ("/api/cmn/numbers", ["GET", "POST"], "get_cmn_numbers"),
    ("/api/cmn/purchase", ["POST"], "purchase_cmn"),
    ("/api/sim/transfer", ["POST"], "transfer_resource"),
    ("/api/inbox", ["GET"], "get_inbox"),
    ("/api/history", ["GET"], "get_transaction_history"),
    ("/logout", ["GET"], "logout"),
    ("/internal/session-cleanup", ["POST"], "session_cleanup"),
]

EXPECTED_OPENAPI_PATHS = sorted(path for path, _, _ in EXPECTED_API_ROUTES)

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
    for route, (_, _, expected_name) in zip(_api_routes(), EXPECTED_API_ROUTES, strict=True):
        assert route.endpoint.__name__ == expected_name


def test_openapi_paths_match_registered_api_routes() -> None:
    paths = sorted(main.app.openapi()["paths"].keys())
    assert paths == EXPECTED_OPENAPI_PATHS


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
        route.path: route.name
        for route in main.app.routes
        if isinstance(route, Mount)
    }
    assert mounts.get("/assets") == "assets"
    # /static is conditional on FRONTEND_STATIC_DIR existing in the environment
    if main.FRONTEND_STATIC_DIR.exists():
        assert mounts.get("/static") == "static"


def test_app_identity_and_create_app_factory() -> None:
    assert main.app is application
    assert main.app is main.application
    assert main.app.title == "3HK New Native FastAPI App"
    assert main.app.version == "1.0.0"
    assert callable(create_app)
    fresh = create_app()
    assert fresh is not main.app
    fresh_paths = [
        route.path for route in fresh.routes if isinstance(route, APIRoute)
    ]
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


# =========================================================================
# Late-bound constant seams — must re-read app.main after registration
# =========================================================================


def _endpoint(path: str) -> Callable[..., Any]:
    for route in _api_routes():
        if route.path == path:
            return route.endpoint
    raise AssertionError(f"route {path} not found")


def test_session_cleanup_reads_live_session_secret(monkeypatch: Any) -> None:
    """SESSION_SECRET is resolved at request time via deps, not closed over."""
    import anyio
    from starlette.requests import Request

    monkeypatch.setattr(main, "SESSION_SECRET", "live-secret-value")

    class FakeRedis:
        def ping(self) -> bool:
            return True

    monkeypatch.setattr(main, "redis_client", FakeRedis())

    endpoint = _endpoint("/internal/session-cleanup")

    def make_request(secret: str) -> Request:
        done = {"flag": False}

        async def receive() -> dict[str, object]:
            if done["flag"]:
                return {"type": "http.disconnect"}
            done["flag"] = True
            return {"type": "http.request", "body": b"{}", "more_body": False}

        return Request(
            {
                "type": "http",
                "method": "POST",
                "path": "/internal/session-cleanup",
                "headers": [(b"x-session-secret", secret.encode())],
                "query_string": b"",
            },
            receive=receive,
        )

    denied = anyio.run(endpoint, make_request("wrong"))
    assert denied.status_code == 401

    allowed = anyio.run(endpoint, make_request("live-secret-value"))
    assert allowed.status_code == 200
    assert allowed.body  # success payload present


def test_session_cleanup_reads_live_redis_client(monkeypatch: Any) -> None:
    """redis_client.ping() is the live main seam after reassignment."""
    import anyio
    from starlette.requests import Request

    calls: list[str] = []

    class TrackingRedis:
        def ping(self) -> bool:
            calls.append("ping")
            return True

    monkeypatch.setattr(main, "SESSION_SECRET", "s")
    monkeypatch.setattr(main, "redis_client", TrackingRedis())

    endpoint = _endpoint("/internal/session-cleanup")
    done = {"flag": False}

    async def receive() -> dict[str, object]:
        if done["flag"]:
            return {"type": "http.disconnect"}
        done["flag"] = True
        return {"type": "http.request", "body": b"{}", "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/internal/session-cleanup",
            "headers": [(b"x-session-secret", b"s")],
            "query_string": b"",
        },
        receive=receive,
    )
    response = anyio.run(endpoint, request)
    assert response.status_code == 200
    assert calls == ["ping"]


def test_check_user_reads_live_base_headers_and_proxies(monkeypatch: Any) -> None:
    """BASE_HEADERS and PROXIES must be taken from app.main at request time."""
    import anyio
    from starlette.requests import Request

    captured: dict[str, object] = {}

    class FakeSession:
        def __enter__(self) -> "FakeSession":
            return self

        def __exit__(self, *_: object) -> None:
            return None

        def post(
            self,
            url: str,
            json: object = None,
            headers: object = None,
            proxies: object = None,
            timeout: object = None,
            **_: object,
        ) -> object:
            captured["url"] = url
            captured["headers"] = headers
            captured["proxies"] = proxies
            captured["timeout"] = timeout
            captured["json"] = json

            class R:
                status_code = 200

                def json(self) -> dict[str, str]:
                    return {"subBrand": "SOSIM"}

            return R()

    monkeypatch.setattr(main, "get_isolated_session", lambda: FakeSession())
    monkeypatch.setattr(
        main,
        "BASE_HEADERS",
        {"Host": "patched.example", "Content-Type": "application/json"},
    )
    monkeypatch.setattr(main, "PROXIES", {"http": "http://proxy.test:8080"})

    endpoint = _endpoint("/api/check-user")
    body = b'{"identifier":"user@example.com"}'
    done = {"flag": False}

    async def receive() -> dict[str, object]:
        if done["flag"]:
            return {"type": "http.disconnect"}
        done["flag"] = True
        return {"type": "http.request", "body": body, "more_body": False}

    request = Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/api/check-user",
            "headers": [
                (b"content-type", b"application/json"),
                (b"user-agent", b"TestAgent/1.0"),
            ],
            "query_string": b"",
        },
        receive=receive,
    )
    response = anyio.run(endpoint, request)
    assert response.status_code == 200
    headers = captured["headers"]
    assert isinstance(headers, dict)
    assert headers["Host"] == "patched.example"
    assert headers["User-Agent"] == "TestAgent/1.0"
    assert captured["proxies"] == {"http": "http://proxy.test:8080"}


def test_profile_reads_live_sub_brands(monkeypatch: Any) -> None:
    """SUB_BRANDS iteration must use the live main seam collection."""
    import anyio
    from starlette.requests import Request

    from app.session_store import SessionContext

    brands_seen: list[str] = []

    def fake_require_login(_: Request) -> SessionContext:
        return SessionContext(
            sid="s",
            data={"accounts": {"a@b.com": {"sub_brand": "THREE"}}},
        )

    def fake_account_context(
        ctx: SessionContext, account_id: str | None
    ) -> dict[str, object]:
        _ = (ctx, account_id)
        return {"cookies": {}, "sub_brand": "THREE"}

    def fake_make(**kwargs: object) -> object:
        url = str(kwargs.get("url", ""))
        # .../THREE/{brand}/user/getProfile
        brand = url.rstrip("/").split("/")[-3]
        brands_seen.append(brand)

        class R:
            status_code = 200

            def json(self) -> dict[str, object]:
                return {"email": "", "subscriptions": []}

        return R()

    monkeypatch.setattr(main, "_require_login", fake_require_login)
    monkeypatch.setattr(main, "get_account_context", fake_account_context)
    monkeypatch.setattr(main, "get_cache", lambda _k: None)
    monkeypatch.setattr(main, "set_cache", lambda *a, **k: None)
    monkeypatch.setattr(main, "make_3hk_request", fake_make)
    monkeypatch.setattr(main, "SUB_BRANDS", ["ALPHA", "BETA"])

    endpoint = _endpoint("/api/profile")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/profile",
            "headers": [],
            "query_string": b"account_id=a%40b.com",
        }
    )
    response = anyio.run(endpoint, request)
    assert response.status_code == 200
    assert brands_seen == ["ALPHA", "BETA"]


def test_readiness_reads_live_paths_and_redis(monkeypatch: Any) -> None:
    """FRONTEND_DIST_DIR, PLANS_CACHE_DIR, redis_client used at request time."""
    from pathlib import Path

    import anyio

    root = Path("/tmp/route-seam-ready")
    dist = root / "dist"
    plans = root / "plans"
    dist.mkdir(parents=True, exist_ok=True)
    plans.mkdir(parents=True, exist_ok=True)
    (dist / "index.html").write_text("i", encoding="utf-8")
    (dist / "login.html").write_text("l", encoding="utf-8")
    (dist / "assets").mkdir(exist_ok=True)
    (dist / "manifest.json").write_text("{}", encoding="utf-8")
    (dist / "sw.js").write_text("//", encoding="utf-8")

    class FakeRedis:
        def ping(self) -> bool:
            return True

    monkeypatch.setattr(main, "FRONTEND_DIST_DIR", dist)
    monkeypatch.setattr(main, "PLANS_CACHE_DIR", plans)
    monkeypatch.setattr(main, "redis_client", FakeRedis())

    endpoint = _endpoint("/_ready")
    response = anyio.run(endpoint)
    assert response.status_code == 200
    import json

    payload = json.loads(response.body)
    assert payload["status"] == "ok"
    assert payload["checks"]["redis"] is True
    assert payload["checks"]["plans_cache_dir"] is True
    assert payload["checks"]["frontend_index"] is True


def test_plans_api_reads_live_plans_cache_dir(monkeypatch: Any) -> None:
    """PLANS_CACHE_DIR seam is used when resolving plans cache path."""
    import json
    from pathlib import Path

    import anyio
    from starlette.requests import Request

    from app.session_store import SessionContext

    root = Path("/tmp/route-seam-plans")
    root.mkdir(parents=True, exist_ok=True)
    cache_file = root / "plans_THREE.json"
    cache_file.write_text(json.dumps({"plans": ["live-seam"]}), encoding="utf-8")

    def fake_require_login(_: Request) -> SessionContext:
        return SessionContext(
            sid="s", data={"accounts": {"a@b.com": {"sub_brand": "THREE"}}}
        )

    def fake_account_context(
        ctx: SessionContext, account_id: str | None
    ) -> dict[str, object]:
        _ = (ctx, account_id)
        return {"cookies": {}}

    monkeypatch.setattr(main, "_require_login", fake_require_login)
    monkeypatch.setattr(main, "get_account_context", fake_account_context)
    monkeypatch.setattr(main, "get_brand_by_sub_id", lambda *a, **k: "THREE")
    monkeypatch.setattr(main, "fetch_and_save_plans_background", lambda *a, **k: None)
    monkeypatch.setattr(main, "PLANS_CACHE_DIR", root)

    endpoint = _endpoint("/api/plans")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/plans",
            "headers": [],
            "query_string": b"account_id=a%40b.com&subscriptionId=sub-1",
        }
    )
    response = anyio.run(endpoint, request)
    assert response.status_code == 200
    body = json.loads(response.body)
    assert body == {"plans": ["live-seam"]}


def test_main_page_reads_live_frontend_dist_dir(monkeypatch: Any) -> None:
    """FRONTEND_DIST_DIR for account page FileResponse is late-bound."""
    from pathlib import Path

    import anyio
    from starlette.requests import Request

    from app.session_store import SessionContext

    root = Path("/tmp/route-seam-frontend")
    root.mkdir(parents=True, exist_ok=True)
    index = root / "index.html"
    index.write_text("<html>live-seam</html>", encoding="utf-8")

    def fake_require_login(_: Request) -> SessionContext:
        return SessionContext(
            sid="s", data={"accounts": {"a@b.com": {"sub_brand": "THREE"}}}
        )

    monkeypatch.setattr(main, "_require_login", fake_require_login)
    monkeypatch.setattr(main, "FRONTEND_DIST_DIR", root)

    endpoint = _endpoint("/main/{account_id}")
    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/main/a@b.com",
            "headers": [],
            "query_string": b"",
            "path_params": {"account_id": "a@b.com"},
        }
    )
    # FastAPI injects path params; call endpoint with kwargs
    response = anyio.run(endpoint, request, "a@b.com")
    assert response.status_code == 200
    # FileResponse path should point at the patched root
    assert Path(response.path) == index
