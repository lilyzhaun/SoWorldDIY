from __future__ import annotations

import logging
from collections.abc import Callable, MutableMapping
from typing import Any, Protocol, runtime_checkable

import requests
from fastapi import Request

from .runtime import BASE_HEADERS, PROXIES
from .session_store import SessionContext
from .upstream_urls import simworld_url

logger = logging.getLogger(__name__)


@runtime_checkable
class UpstreamDepsProtocol(Protocol):
    """Read-only dependency surface for upstream request helpers.

    Members are ``@property`` so adapters like ``MainDepsAdapter`` (which
    re-read live ``main`` seams for monkeypatch targets) structurally satisfy
    this protocol without mutable attribute assignment.
    """

    @property
    def decrypt_password(self) -> Callable[[str | None], str | None]: ...

    @property
    def get_isolated_session(self) -> Callable[[], requests.Session]: ...

    @property
    def _save_session(self) -> Callable[[SessionContext], None]: ...

    @property
    def resolve_proxies(
        self,
    ) -> Callable[
        [str, MutableMapping[str, str] | None], MutableMapping[str, str] | None
    ]: ...

    @property
    def attempt_silent_relogin(
        self,
    ) -> Callable[[Request, SessionContext, str, dict[str, Any]], bool]: ...

    @property
    def get_account_context(
        self,
    ) -> Callable[[SessionContext, str | None], dict[str, Any] | None]: ...

    @property
    def make_3hk_request(self) -> Callable[..., requests.Response | None]: ...


_upstream_deps_provider: Callable[[], UpstreamDepsProtocol] | None = None


def configure_upstream_deps(provider: Callable[[], UpstreamDepsProtocol]) -> None:
    global _upstream_deps_provider
    _upstream_deps_provider = provider


def _deps() -> UpstreamDepsProtocol:
    if _upstream_deps_provider is None:
        raise RuntimeError("upstream deps not configured; call configure_upstream_deps")
    return _upstream_deps_provider()


def attempt_silent_relogin(
    request: Request,
    ctx: SessionContext,
    account_id: str,
    account_data: dict[str, Any],
) -> bool:
    d = _deps()
    if account_data.get("login_type") != "password" or not account_data.get(
        "stored_password_encrypted"
    ):
        return False

    password = d.decrypt_password(str(account_data.get("stored_password_encrypted")))
    if not password:
        return False
    sub_brand = str(account_data.get("sub_brand", "THREE"))
    login_url = simworld_url(sub_brand, "user/login/")
    payload = {
        "id": account_id,
        "password": password,
        "rememberMe": True,
        "forceLogin": False,
    }

    headers = dict(BASE_HEADERS)
    headers["User-Agent"] = request.headers.get("User-Agent", "Mozilla/5.0")

    try:
        with d.get_isolated_session() as s:
            r = s.post(
                login_url, json=payload, headers=headers, proxies=PROXIES, timeout=10
            )
            if r.status_code == 204:
                new_cookies = requests.utils.dict_from_cookiejar(r.cookies)
                accounts = ctx.data.get("accounts", {})
                if account_id in accounts:
                    accounts[account_id]["cookies"] = new_cookies
                    ctx.data["accounts"] = accounts
                    d._save_session(ctx)
                    logger.info("Silent re-login successful for %s", account_id)
                    return True
    except Exception as exc:
        logger.error("Silent re-login error: %s", exc)
    return False


def make_3hk_request(
    request: Request,
    ctx: SessionContext,
    method: str,
    url: str,
    json_data: Any = None,
    params: dict[str, Any] | None = None,
    account_id: str | None = None,
    account_context: dict[str, Any] | None = None,
    _is_retry: bool = False,
) -> requests.Response | None:
    d = _deps()
    if not account_context:
        logger.error("make_3hk_request called without account_context")
        return None

    cookies = account_context.get("cookies", {})
    headers = dict(BASE_HEADERS)
    headers["User-Agent"] = request.headers.get("User-Agent", "Mozilla/5.0")

    try:
        with d.get_isolated_session() as s:
            s.cookies.update(cookies)
            response = s.request(
                method,
                url,
                headers=headers,
                params=params,
                json=json_data,
                proxies=d.resolve_proxies(url, PROXIES),
                timeout=(5, 15),
            )

            if response.status_code == 401:
                target_id = account_id
                if not target_id:
                    for uid, data in ctx.data.get("accounts", {}).items():
                        if data is account_context:
                            target_id = uid
                            break
                if target_id and not _is_retry:
                    logger.info("401 for %s, trying silent relogin", target_id)
                    if d.attempt_silent_relogin(
                        request, ctx, target_id, account_context
                    ):
                        refreshed_ctx = d.get_account_context(ctx, target_id)
                        return d.make_3hk_request(
                            request=request,
                            ctx=ctx,
                            method=method,
                            url=url,
                            json_data=json_data,
                            params=params,
                            account_id=target_id,
                            account_context=refreshed_ctx,
                            _is_retry=True,
                        )
                    logger.warning("Relogin failed for %s", target_id)
                return response

            if response.cookies:
                new_cookies = requests.utils.dict_from_cookiejar(response.cookies)
                if new_cookies:
                    account_context.setdefault("cookies", {})
                    account_context["cookies"].update(new_cookies)
                    if account_id:
                        accounts = ctx.data.get("accounts", {})
                        if account_id in accounts:
                            accounts[account_id] = account_context
                            ctx.data["accounts"] = accounts
                    d._save_session(ctx)

            return response
    except Exception as exc:
        logger.error("Request Error: %s", exc)
        return None
