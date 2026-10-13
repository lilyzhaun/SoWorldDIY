from __future__ import annotations

import logging
from urllib.parse import quote

from fastapi import FastAPI, Request
from fastapi.responses import (
    FileResponse,
    JSONResponse,
    PlainTextResponse,
    RedirectResponse,
)
from redis.exceptions import RedisError
from starlette.responses import Response

from ..blocking import run_blocking
from ..metrics import authorize_metrics, render_metrics, set_app_ready, set_redis_ready
from ..public_errors import SERVICE_UNAVAILABLE, UNAUTHORIZED
from ..rate_limit_http import client_ip, guard
from ..responses import _public_error
from .deps import RouteDeps

logger = logging.getLogger(__name__)


def register_system_routes(app: FastAPI, deps: RouteDeps) -> None:
    @app.get("/_health")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    async def readiness_checks() -> dict[str, bool]:
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
            checks["redis"] = bool(await run_blocking(deps.redis_client.ping))
        except RedisError:
            checks["redis"] = False
        set_redis_ready(bool(checks["redis"]))
        set_app_ready(all(checks.values()))
        return checks

    @app.get("/_ready")
    async def readiness() -> JSONResponse:
        checks = await readiness_checks()
        status_code = 200 if all(checks.values()) else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ok" if status_code == 200 else "error",
                "checks": checks,
            },
        )

    @app.get("/metrics")
    async def metrics(request: Request) -> Response:
        decision = authorize_metrics(
            request.headers.get("x-metrics-secret"),
            deps.METRICS_SECRET,
        )
        if decision == "missing":
            # Do not advertise the endpoint without a secret.
            return Response(status_code=404)
        if decision != "ok":
            return _public_error(UNAUTHORIZED, 403)
        await readiness_checks()
        body, content_type = render_metrics()
        return PlainTextResponse(content=body.decode("utf-8"), media_type=content_type)

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
        if ctx is None:
            blocked = guard(
                await run_blocking(
                    deps.rate_limiter.session_create_ip,
                    client_ip(request, deps.TRUSTED_PROXY_IPS),
                ),
                endpoint="session_create",
            )
            if blocked is not None:
                return blocked
            try:
                ctx = await run_blocking(deps._create_session)
            except RuntimeError:
                return _public_error(SERVICE_UNAVAILABLE, 503)
            request.state.session_ctx = ctx
            request.state.delete_session_cookie = False
        if request.query_params.get("add") == "1":
            return FileResponse(
                deps.FRONTEND_DIST_DIR / "login.html", media_type="text/html"
            )

        accounts = ctx.data.get("accounts", {}) if ctx else {}
        if isinstance(accounts, dict) and accounts:
            first_id = list(accounts.keys())[0]
            return RedirectResponse(
                url=f"/main/{quote(first_id, safe='@')}", status_code=302
            )
        return FileResponse(
            deps.FRONTEND_DIST_DIR / "login.html", media_type="text/html"
        )
