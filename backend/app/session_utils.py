from __future__ import annotations

import logging
import time
from collections.abc import Callable, Mapping, MutableMapping
from typing import Any, Final, Protocol, runtime_checkable

from fastapi import Request
from fastapi.responses import JSONResponse
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from . import runtime as _runtime
from .public_errors import CSRF_INVALID
from .responses import _public_error
from .runtime import (
    CSRF_COOKIE_NAME,
    CSRF_HEADER_NAME,
    SESSION_COOKIE_NAME,
    SESSION_DAILY_REFRESH_SECONDS,
    SESSION_LIFETIME_SECONDS,
)
from .runtime import (
    session_store as _default_store,
)
from .security import csrf_token_matches, new_csrf_token
from .session_store import SessionContext

logger = logging.getLogger(__name__)

_LEGACY_ACCOUNT_SECRET_KEYS: Final[tuple[str, ...]] = ("credential", "auth_code")


def scrub_legacy_account_secrets(session_data: MutableMapping[str, Any]) -> bool:
    accounts = session_data.get("accounts")
    if not isinstance(accounts, Mapping):
        return False

    changed = False
    for account in accounts.values():
        if not isinstance(account, MutableMapping):
            continue
        for key in _LEGACY_ACCOUNT_SECRET_KEYS:
            if key in account:
                del account[key]
                changed = True
    return changed


@runtime_checkable
class SessionStoreProtocol(Protocol):
    def load(self, sid: str) -> dict[str, Any] | None: ...
    def create(self, data: dict[str, Any]) -> SessionContext: ...
    def save(self, sid: str, data: dict[str, Any]) -> None: ...
    def delete(self, sid: str) -> None: ...


class ValidateCsrfFn(Protocol):
    def __call__(
        self,
        request: Request,
        ctx: SessionContext | None,
    ) -> JSONResponse | None: ...


def _default_session_store() -> SessionStoreProtocol:
    return _default_store


_session_store_provider: Callable[[], SessionStoreProtocol] = _default_session_store


def configure_session_store(provider: Callable[[], SessionStoreProtocol]) -> None:
    global _session_store_provider
    _session_store_provider = provider


def _store() -> SessionStoreProtocol:
    return _session_store_provider()


def _get_session_if_exists(request: Request) -> SessionContext | None:
    sid = request.cookies.get(SESSION_COOKIE_NAME)
    if not sid:
        return None

    store = _store()
    redis_data = store.load(sid)
    if redis_data is not None:
        if scrub_legacy_account_secrets(redis_data):
            store.save(sid, redis_data)
        return SessionContext(sid=sid, data=redis_data)

    return None


def _create_session() -> SessionContext:
    data: dict[str, Any] = {"csrf_token": new_csrf_token()}
    return _store().create(data)


def _save_session(ctx: SessionContext) -> None:
    _store().save(ctx.sid, ctx.data)


def _clear_session(ctx: SessionContext) -> None:
    _store().delete(ctx.sid)
    ctx.data.clear()


def _mark_session_cookie_for_deletion(request: Request) -> None:
    request.state.session_ctx = None
    request.state.delete_session_cookie = True


def _daily_refresh_session_if_needed(ctx: SessionContext) -> None:
    accounts = ctx.data.get("accounts")
    changed = False
    if not ctx.data.get("csrf_token"):
        ctx.data["csrf_token"] = new_csrf_token()
        changed = True
    if accounts:
        now = time.time()
        last_refresh = float(ctx.data.get("last_session_refresh", 0) or 0)
        if now - last_refresh > SESSION_DAILY_REFRESH_SECONDS:
            ctx.data["last_session_refresh"] = now
            changed = True
    if changed:
        _save_session(ctx)


def _ensure_csrf_token(ctx: SessionContext) -> str:
    token = ctx.data.get("csrf_token")
    if not isinstance(token, str) or not token:
        token = new_csrf_token()
        ctx.data["csrf_token"] = token
        _save_session(ctx)
    return token


def _validate_csrf(request: Request, ctx: SessionContext | None) -> JSONResponse | None:
    if ctx is None:
        return None
    expected = ctx.data.get("csrf_token")
    provided = request.headers.get(CSRF_HEADER_NAME)
    if not csrf_token_matches(str(expected) if expected else None, provided):
        return _public_error(CSRF_INVALID, 403)
    return None


def get_account_context(
    ctx: SessionContext, account_id: str | None
) -> dict[str, Any] | None:
    if not account_id:
        return None
    accounts = ctx.data.get("accounts", {})
    account = accounts.get(account_id)
    if isinstance(account, dict):
        return account
    return None


class SessionMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next: Any) -> Response:
        ctx = _get_session_if_exists(request)
        request.state.session_ctx = ctx
        request.state.delete_session_cookie = False
        if ctx is None and request.cookies.get(SESSION_COOKIE_NAME):
            request.state.delete_session_cookie = True
        if ctx is not None:
            _daily_refresh_session_if_needed(ctx)
        response = await call_next(request)
        current_ctx = getattr(request.state, "session_ctx", None)
        secure = bool(_runtime.COOKIE_SECURE)
        if getattr(request.state, "delete_session_cookie", False):
            response.delete_cookie(key=SESSION_COOKIE_NAME, path="/", secure=secure)
            response.delete_cookie(key=CSRF_COOKIE_NAME, path="/", secure=secure)
        elif current_ctx is not None:
            csrf_token = _ensure_csrf_token(current_ctx)
            response.set_cookie(
                key=SESSION_COOKIE_NAME,
                value=current_ctx.sid,
                max_age=SESSION_LIFETIME_SECONDS,
                httponly=True,
                samesite="lax",
                path="/",
                secure=secure,
            )
            response.set_cookie(
                key=CSRF_COOKIE_NAME,
                value=csrf_token,
                max_age=SESSION_LIFETIME_SECONDS,
                httponly=False,
                samesite="lax",
                path="/",
                secure=secure,
            )
        return response


def _require_login(request: Request) -> SessionContext | None:
    ctx = getattr(request.state, "session_ctx", None)
    if ctx is None:
        return None
    accounts = ctx.data.get("accounts", {})
    if not isinstance(accounts, dict) or not accounts:
        return None
    return ctx
