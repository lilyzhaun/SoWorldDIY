from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, RedirectResponse
from starlette.responses import Response

from .deps import RouteDeps

logger = logging.getLogger(__name__)

def register_account_page_routes(app: FastAPI, deps: RouteDeps) -> None:
    @app.get("/main")
    async def main_page_default(request: Request) -> RedirectResponse:
        ctx = deps._require_login(request)
        if not ctx:
            return RedirectResponse(url="/", status_code=302)
        accounts = ctx.data.get("accounts", {})
        first_id = list(accounts.keys())[0]
        return RedirectResponse(url=f"/main/{first_id}", status_code=302)

    @app.get("/main/{account_id}")
    async def main_page(request: Request, account_id: str) -> Response:
        ctx = deps._require_login(request)
        if not ctx:
            return RedirectResponse(url="/", status_code=302)

        accounts = ctx.data.get("accounts", {})
        if account_id not in accounts:
            return RedirectResponse(url="/", status_code=302)
        return FileResponse(deps.FRONTEND_DIST_DIR / "index.html", media_type="text/html")
