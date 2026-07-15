"""Module-backed late-bound dependency adapter for ``app.main``.

Stores a reference to the live main module (or any object with the same
attribute surface) and re-reads each seam on every property access. This keeps
``monkeypatch.setattr(main, ...)`` visible to routes, upstream, and services
without caching snapshots or reading ``globals()``.

This module must not import ``app.main`` (composition is inverted: main injects
itself after seams are defined).
"""

from __future__ import annotations

from collections.abc import Callable, MutableMapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import redis
import requests
from fastapi import Request

from .responses import (
    JsonErrorFn,
    JsonSuccessFn,
    RedirectToLoginFn,
    UpstreamErrorFn,
)
from .runtime import SetCacheFn
from .services import FetchPlansBackgroundFn, SendPurchaseeventsFn
from .session_store import SessionContext
from .session_utils import SessionStoreProtocol, ValidateCsrfFn
from .upstream import Make3hkRequestFn


class MainModuleSource(Protocol):
    """Structural surface of the ``app.main`` module that the adapter re-reads."""

    session_store: SessionStoreProtocol
    decrypt_password: Callable[[str | None], str | None]
    get_isolated_session: Callable[[], requests.Session]
    _save_session: Callable[[SessionContext], None]
    resolve_proxies: Callable[[str, dict[str, str] | None], dict[str, str] | None]
    attempt_silent_relogin: Callable[
        [Request, SessionContext, str, dict[str, Any]], bool
    ]
    get_account_context: Callable[[SessionContext, str | None], dict[str, Any] | None]
    make_3hk_request: Make3hkRequestFn
    get_cache: Callable[[str], Any | None]
    set_cache: SetCacheFn
    delete_cache: Callable[[str], None]
    notify: Callable[[str], None]
    plans_refreshing: set[str]
    verify_auth_code: Callable[[Any, bool], tuple[bool, str]]
    _json_success: JsonSuccessFn
    _json_error: JsonErrorFn
    _upstream_error: UpstreamErrorFn
    _create_session: Callable[[], SessionContext]
    encrypt_password: Callable[[str | None], str | None]
    _require_login: Callable[[Request], SessionContext | None]
    get_brand_by_sub_id: Callable[[SessionContext, str | None, str | None], str]
    fetch_and_save_plans_background: FetchPlansBackgroundFn
    _redirect_to_login: RedirectToLoginFn
    _validate_csrf: ValidateCsrfFn
    handle_purchase_event: SendPurchaseeventsFn
    internal_logout_account: Callable[[SessionContext, str], bool]
    _mark_session_cookie_for_deletion: Callable[[Request], None]
    _clear_session: Callable[[SessionContext], None]
    BASE_HEADERS: MutableMapping[str, str]
    PROXIES: dict[str, str] | None
    SUB_BRANDS: Sequence[str]
    FRONTEND_DIST_DIR: Path
    PLANS_CACHE_DIR: Path
    SESSION_SECRET: str
    redis_client: redis.Redis


@dataclass(frozen=True, slots=True)
class MainDepsAdapter:
    """Explicit late-bound adapter over a main-module source object.

    Each property forwards to ``self.source.<name>`` with no caching, so
    reassignment of attributes on the source is immediately visible.
    """

    source: MainModuleSource

    @property
    def session_store(self) -> SessionStoreProtocol:
        return self.source.session_store

    @property
    def decrypt_password(self) -> Callable[[str | None], str | None]:
        return self.source.decrypt_password

    @property
    def get_isolated_session(self) -> Callable[[], requests.Session]:
        return self.source.get_isolated_session

    @property
    def _save_session(self) -> Callable[[SessionContext], None]:
        return self.source._save_session

    @property
    def resolve_proxies(
        self,
    ) -> Callable[[str, dict[str, str] | None], dict[str, str] | None]:
        return self.source.resolve_proxies

    @property
    def attempt_silent_relogin(
        self,
    ) -> Callable[[Request, SessionContext, str, dict[str, Any]], bool]:
        return self.source.attempt_silent_relogin

    @property
    def get_account_context(
        self,
    ) -> Callable[[SessionContext, str | None], dict[str, Any] | None]:
        return self.source.get_account_context

    @property
    def make_3hk_request(self) -> Make3hkRequestFn:
        return self.source.make_3hk_request

    @property
    def get_cache(self) -> Callable[[str], Any | None]:
        return self.source.get_cache

    @property
    def set_cache(self) -> SetCacheFn:
        return self.source.set_cache

    @property
    def delete_cache(self) -> Callable[[str], None]:
        return self.source.delete_cache

    @property
    def notify(self) -> Callable[[str], None]:
        return self.source.notify

    @property
    def plans_refreshing(self) -> set[str]:
        return self.source.plans_refreshing

    @property
    def verify_auth_code(self) -> Callable[[Any, bool], tuple[bool, str]]:
        return self.source.verify_auth_code

    @property
    def _json_success(self) -> JsonSuccessFn:
        return self.source._json_success

    @property
    def _json_error(self) -> JsonErrorFn:
        return self.source._json_error

    @property
    def _upstream_error(self) -> UpstreamErrorFn:
        return self.source._upstream_error

    @property
    def _create_session(self) -> Callable[[], SessionContext]:
        return self.source._create_session

    @property
    def encrypt_password(self) -> Callable[[str | None], str | None]:
        return self.source.encrypt_password

    @property
    def _require_login(self) -> Callable[[Request], SessionContext | None]:
        return self.source._require_login

    @property
    def get_brand_by_sub_id(
        self,
    ) -> Callable[[SessionContext, str | None, str | None], str]:
        return self.source.get_brand_by_sub_id

    @property
    def fetch_and_save_plans_background(self) -> FetchPlansBackgroundFn:
        return self.source.fetch_and_save_plans_background

    @property
    def _redirect_to_login(self) -> RedirectToLoginFn:
        return self.source._redirect_to_login

    @property
    def _validate_csrf(self) -> ValidateCsrfFn:
        return self.source._validate_csrf

    @property
    def handle_purchase_event(self) -> SendPurchaseeventsFn:
        return self.source.handle_purchase_event

    @property
    def internal_logout_account(self) -> Callable[[SessionContext, str], bool]:
        return self.source.internal_logout_account

    @property
    def _mark_session_cookie_for_deletion(self) -> Callable[[Request], None]:
        return self.source._mark_session_cookie_for_deletion

    @property
    def _clear_session(self) -> Callable[[SessionContext], None]:
        return self.source._clear_session

    @property
    def BASE_HEADERS(self) -> MutableMapping[str, str]:
        return self.source.BASE_HEADERS

    @property
    def PROXIES(self) -> dict[str, str] | None:
        return self.source.PROXIES

    @property
    def SUB_BRANDS(self) -> Sequence[str]:
        return self.source.SUB_BRANDS

    @property
    def FRONTEND_DIST_DIR(self) -> Path:
        return self.source.FRONTEND_DIST_DIR

    @property
    def PLANS_CACHE_DIR(self) -> Path:
        return self.source.PLANS_CACHE_DIR

    @property
    def SESSION_SECRET(self) -> str:
        return self.source.SESSION_SECRET

    @property
    def redis_client(self) -> redis.Redis:
        return self.source.redis_client
