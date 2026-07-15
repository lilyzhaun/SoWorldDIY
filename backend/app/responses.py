from __future__ import annotations

import logging
import uuid
from collections.abc import Mapping
from typing import Any, Protocol

import requests
from fastapi.responses import JSONResponse, RedirectResponse
from starlette.responses import Response

from .public_errors import PublicError

__all__ = [
    "JsonErrorFn",
    "JsonSuccessFn",
    "RedirectToLoginFn",
    "UpstreamErrorFn",
    "_json_error",
    "_json_success",
    "_public_error",
    "_redirect_to_login",
    "_upstream_error",
    "json_error",
    "json_success",
    "redirect_to_login",
    "upstream_error",
]

logger = logging.getLogger(__name__)


class JsonErrorFn(Protocol):
    def __call__(self, message: str, status_code: int = 400) -> JSONResponse: ...


class JsonSuccessFn(Protocol):
    def __call__(self, content: Mapping[str, object]) -> JSONResponse: ...


class UpstreamErrorFn(Protocol):
    def __call__(
        self,
        response: requests.Response | None,
        public_message: str = "请求失败，请稍后重试",
        status_code: int = 400,
        *,
        operation: str = "upstream",
        correlation_id: str | None = None,
    ) -> JSONResponse: ...


class RedirectToLoginFn(Protocol):
    def __call__(self) -> Response: ...


def _json_error(message: str, status_code: int = 400) -> JSONResponse:
    return JSONResponse(
        status_code=status_code, content={"status": "error", "message": message}
    )


def _public_error(error: PublicError, status_code: int) -> JSONResponse:
    """Return a stable public error without internal details."""
    return _json_error(error.message, status_code)


def _upstream_error(
    response: requests.Response | None,
    public_message: str = "请求失败，请稍后重试",
    status_code: int = 400,
    *,
    operation: str = "upstream",
    correlation_id: str | None = None,
) -> JSONResponse:
    cid = correlation_id or uuid.uuid4().hex[:12]
    if response is None:
        logger.warning(
            "Upstream request failed operation=%s status=none error_class=NoResponse correlation_id=%s",
            operation,
            cid,
        )
    else:
        logger.warning(
            "Upstream request failed operation=%s status=%s error_class=HTTPError correlation_id=%s",
            operation,
            response.status_code,
            cid,
        )
    return _json_error(public_message, status_code)


def _json_success(content: dict[str, Any]) -> JSONResponse:
    return JSONResponse(status_code=200, content=content)


def _redirect_to_login() -> RedirectResponse:
    return RedirectResponse(url="/", status_code=302)


# Public aliases (compat layer; keep underscore names for monkeypatch seams)
json_error = _json_error
json_success = _json_success
upstream_error = _upstream_error
redirect_to_login = _redirect_to_login
