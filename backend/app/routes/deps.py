from __future__ import annotations

from collections.abc import Callable, MutableMapping, Sequence
from pathlib import Path
from typing import Any, Protocol, runtime_checkable

import redis
import requests
from fastapi import Request

from ..responses import (
    JsonErrorFn,
    JsonSuccessFn,
    RedirectToLoginFn,
    UpstreamErrorFn,
)
from ..runtime import SetCacheFn
from ..services import FetchPlansBackgroundFn, SendPurchaseeventsFn
from ..session_store import SessionContext
from ..session_utils import ValidateCsrfFn
from ..upstream import Make3hkRequestFn


@runtime_checkable
class RouteDeps(Protocol):
    """Late-bound dependency surface for route handlers.

    Members are ``@property`` so adapters re-read live ``app.main`` seams and
    monkeypatch targets stay visible after registration.
    """

    @property
    def get_isolated_session(self) -> Callable[[], requests.Session]: ...

    @property
    def verify_auth_code(self) -> Callable[[Any, bool], tuple[bool, str]]: ...

    @property
    def _json_success(self) -> JsonSuccessFn: ...

    @property
    def _json_error(self) -> JsonErrorFn: ...

    @property
    def _upstream_error(self) -> UpstreamErrorFn: ...

    @property
    def _create_session(self) -> Callable[[], SessionContext]: ...

    @property
    def encrypt_password(self) -> Callable[[str | None], str | None]: ...

    @property
    def _save_session(self) -> Callable[[SessionContext], None]: ...

    @property
    def notify(self) -> Callable[[str], None]: ...

    @property
    def _require_login(self) -> Callable[[Request], SessionContext | None]: ...

    @property
    def get_account_context(
        self,
    ) -> Callable[[SessionContext, str | None], dict[str, Any] | None]: ...

    @property
    def delete_cache(self) -> Callable[[str], None]: ...

    @property
    def get_cache(self) -> Callable[[str], Any | None]: ...

    @property
    def set_cache(self) -> SetCacheFn: ...

    @property
    def make_3hk_request(self) -> Make3hkRequestFn: ...

    @property
    def get_brand_by_sub_id(
        self,
    ) -> Callable[[SessionContext, str | None, str | None], str]: ...

    @property
    def fetch_and_save_plans_background(self) -> FetchPlansBackgroundFn: ...

    @property
    def _redirect_to_login(self) -> RedirectToLoginFn: ...

    @property
    def _validate_csrf(self) -> ValidateCsrfFn: ...

    @property
    def handle_purchase_event(self) -> SendPurchaseeventsFn: ...

    @property
    def internal_logout_account(
        self,
    ) -> Callable[[SessionContext, str], bool]: ...

    @property
    def _mark_session_cookie_for_deletion(self) -> Callable[[Request], None]: ...

    @property
    def _clear_session(self) -> Callable[[SessionContext], None]: ...

    @property
    def BASE_HEADERS(self) -> MutableMapping[str, str]: ...

    @property
    def PROXIES(self) -> dict[str, str] | None: ...

    @property
    def SUB_BRANDS(self) -> Sequence[str]: ...

    @property
    def FRONTEND_DIST_DIR(self) -> Path: ...

    @property
    def PLANS_CACHE_DIR(self) -> Path: ...

    @property
    def SESSION_SECRET(self) -> str: ...

    @property
    def redis_client(self) -> redis.Redis: ...
