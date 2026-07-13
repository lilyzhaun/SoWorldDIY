from __future__ import annotations

from collections.abc import Callable
from typing import Any

from fastapi.routing import APIRoute

from app import main


def _endpoint(path: str) -> Callable[..., Any]:
    for route in main.app.routes:
        if isinstance(route, APIRoute) and route.path == path:
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
        def __enter__(self) -> FakeSession:
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
