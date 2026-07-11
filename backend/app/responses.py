from __future__ import annotations

import logging
from typing import Any

import requests
from fastapi.responses import JSONResponse, RedirectResponse

logger = logging.getLogger(__name__)


def _json_error(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"status": "error", "message": message}
    )


def _upstream_error(
    response: requests.Response | None,
    public_message: str = "请求失败，请稍后重试",
    status_code: int = 400,
) -> JSONResponse:
    if response is None:
        logger.warning("Upstream request failed without response")
    else:
        logger.warning(
            "Upstream request failed: status=%s body=%s",
            response.status_code,
            response.text[:1000],
        )
    return _json_error(public_message, status_code)


def _json_success(content: dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=200, content=content)


def _redirect_to_login() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=302)
