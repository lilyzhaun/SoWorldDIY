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
