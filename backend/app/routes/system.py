from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from redis.exceptions import RedisError
from starlette.responses import Response

from .deps import RouteDeps

logger = logging.getLogger(__name__)


def register_system_routes(app: FastAPI, deps: RouteDeps) -> None:
    @app.get("/_health")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/_ready")
    async def readiness() -> JSONResponse:
        checks: dict[str, bool] = {
            "redis": False,
            "frontend_index": (deps.FRONTEND_DIST_DIR / "index.html").exists(),
            "frontend_login": (deps.FRONTEND_DIST_DIR / "login.html").exists(),
            "frontend_assets": (deps.FRONTEND_DIST_DIR / "assets").exists(),
            "frontend_manifest": (deps.FRONTEND_DIST_DIR / "manifest.json").exists(),
            "frontend_sw": (deps.FRONTEND_DIST_DIR / "sw.js").exists(),
            "plans_cache_dir": deps.PLANS_CACHE_DIR.exists(),
        }
        try:
            checks["redis"] = bool(deps.redis_client.ping())
        except RedisError:
            checks["redis"] = False
        status_code = 200 if all(checks.values()) else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ok" if status_code == 200 else "error",
                "checks": checks,
            },
        )

    @app.get("/manifest.json")
    async def manifest() -> FileResponse:
        return FileResponse(
            deps.FRONTEND_DIST_DIR / "manifest.json",
            media_type="application/manifest+json",
        )

    @app.get("/sw.js")
    async def service_worker() -> FileResponse:
        return FileResponse(
            deps.FRONTEND_DIST_DIR / "sw.js", media_type="application/javascript"
        )

    @app.get("/favicon.ico")
    async def favicon() -> FileResponse:
        return FileResponse(
            deps.FRONTEND_DIST_DIR / "static/images/icon-192.png",
            media_type="image/png",
        )

    @app.get("/")
    async def index(request: Request) -> Response:
        ctx = getattr(request.state, "session_ctx", None)
        if request.query_params.get("add") == "1":
            return FileResponse(
                deps.FRONTEND_DIST_DIR / "login.html", media_type="text/html"
            )

        accounts = ctx.data.get("accounts", {}) if ctx else {}
        if isinstance(accounts, dict) and accounts:
            first_id = list(accounts.keys())[0]
            return RedirectResponse(url=f"/main/{first_id}", status_code=302)
        return FileResponse(
            deps.FRONTEND_DIST_DIR / "login.html", media_type="text/html"
        )
