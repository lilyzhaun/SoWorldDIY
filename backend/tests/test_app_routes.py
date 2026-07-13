import json
from collections.abc import Awaitable, Callable

import anyio
from fastapi.routing import APIRoute
from pytest import MonkeyPatch
from starlette.requests import Request
from starlette.responses import Response


def test_app_routes_available(monkeypatch: MonkeyPatch) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app.main import app

    routes = {route.path for route in app.routes if isinstance(route, APIRoute)}
    assert "/_health" in routes
    assert "/_ready" in routes
    assert "/api/purchase" in routes


def test_cmn_numbers_holds_nine_numbers_for_three_by_three_grid(
    monkeypatch: MonkeyPatch,
) -> None:
    monkeypatch.setenv("SESSION_SECRET", "test-secret")
    from app import main
    from app.session_store import SessionContext

    captured_urls: list[str] = []

    class UpstreamResponse:
        status_code: int = 200

        def json(self) -> dict[str, list[str]]:
            return {
                "lineList": [
                    "10000009",
                    "10000008",
                    "10000007",
                    "10000006",
                    "10000005",
                    "10000004",
                    "10000003",
                    "10000002",
                    "10000001",
                    "10000000",
                ]
            }

    def require_login(_: Request) -> SessionContext:
        return SessionContext(sid="test", data={"accounts": {"acct@example.com": {}}})

    def account_context(
        ctx: SessionContext, account_id: str | None
    ) -> dict[str, dict[str, str]]:
        _ = (ctx, account_id)
        return {"cookies": {}}

    def brand_by_sub_id(
        ctx: SessionContext, sub_id: str | None, account_id: str | None
    ) -> str:
        _ = (ctx, sub_id, account_id)
        return "THREE"

    monkeypatch.setattr(main, "_require_login", require_login)
    monkeypatch.setattr(main, "get_account_context", account_context)
    monkeypatch.setattr(main, "get_brand_by_sub_id", brand_by_sub_id)

    def fake_make_3hk_request(
        *,
        request: Request,
        ctx: SessionContext,
        method: str,
        url: str,
        json_data: dict[str, str | int | bool | None] | list[str] | None = None,
        params: dict[str, str | int | bool | None] | None = None,
        account_id: str | None = None,
        account_context: dict[str, dict[str, str]] | None = None,
        _is_retry: bool = False,
    ) -> UpstreamResponse:
        _ = (
            request,
            ctx,
            method,
            json_data,
            params,
            account_id,
            account_context,
            _is_retry,
        )
        captured_urls.append(url)
        return UpstreamResponse()

    monkeypatch.setattr(main, "make_3hk_request", fake_make_3hk_request)

    request = Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/api/cmn/numbers",
            "headers": [],
            "query_string": b"account_id=acct%40example.com&subscriptionId=sub-1",
        }
    )
    endpoint: Callable[[Request], Awaitable[Response]] | None = None
    for route in main.app.routes:
        if isinstance(route, APIRoute) and route.path == "/api/cmn/numbers":
            endpoint = route.endpoint
            break
    assert endpoint is not None

    response = anyio.run(endpoint, request)

    assert isinstance(response, Response)
    assert response.status_code == 200
    assert json.loads(bytes(response.body)) == {
        "status": "success",
        "numbers": [
            "10000000",
            "10000001",
            "10000002",
            "10000003",
            "10000004",
            "10000005",
            "10000006",
            "10000007",
            "10000008",
        ],
    }
    assert captured_urls == [
        "https://simworld.net/SIMworldApi-pro/HTHK/THREE/THREE/mnms/holdAvailableNumbersFor15m/9/"
    ]
