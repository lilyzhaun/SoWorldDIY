from __future__ import annotations

import logging
from collections.abc import Callable, MutableMapping, Sequence
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import redis
import requests
from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles

from .delivery_extension import send as notify  # noqa: F401 — re-exported for monkeypatch seam
from .request_overrides import (
    resolve_proxies,  # noqa: F401 — re-exported for monkeypatch seam
)
from .responses import (  # noqa: F401 — re-exported for monkeypatch seam
    _json_error,
    _json_success,
    _redirect_to_login,
    _upstream_error,
)
from .routes import (
    register_account_page_routes,
    register_auth_routes,
    register_cmn_routes,
    register_commerce_routes,
    register_messages_routes,
    register_profile_routes,
    register_session_routes,
    register_system_routes,
    register_transfer_routes,
)
from .runtime import (
    BASE_HEADERS,  # noqa: F401 — re-exported for monkeypatch seam
    FRONTEND_DIST_DIR,
    FRONTEND_STATIC_DIR,
    PLANS_CACHE_DIR,  # noqa: F401 — re-exported for monkeypatch seam
    PROXIES,  # noqa: F401 — re-exported for monkeypatch seam
    SESSION_SECRET,  # noqa: F401 — re-exported for monkeypatch seam
    SUB_BRANDS,  # noqa: F401 — re-exported for monkeypatch seam
    auth_code_store,
    decrypt_password,  # noqa: F401 — re-exported for monkeypatch seam
    delete_cache,  # noqa: F401 — re-exported for monkeypatch seam
    encrypt_password,  # noqa: F401 — re-exported for monkeypatch seam
    get_cache,  # noqa: F401 — re-exported for monkeypatch seam
    get_isolated_session,  # noqa: F401 — re-exported for monkeypatch seam
    plans_refresh_lock,  # noqa: F401 — re-exported for monkeypatch seam
    plans_refreshing,  # noqa: F401 — re-exported for monkeypatch seam
    redis_client,  # noqa: F401 — re-exported for monkeypatch seam
    session_store,  # noqa: F401 — re-exported for monkeypatch seam
    set_cache,  # noqa: F401 — re-exported for monkeypatch seam
    verify_auth_code,  # noqa: F401 — re-exported for monkeypatch seam
)
from .services import (  # noqa: F401 — re-exported for monkeypatch seam
    configure_service_deps,
    fetch_and_save_plans_background,
    get_brand_by_sub_id,
    handle_purchase_event,
)
from .session_store import SessionContext
from .session_utils import (  # noqa: F401 — re-exported for monkeypatch seam
    SessionMiddleware,
    SessionStoreProtocol,
    _clear_session,
    _create_session,
    _mark_session_cookie_for_deletion,
    _require_login,
    _save_session,
    _validate_csrf,
    configure_session_store,
    get_account_context,
)
from .upstream import (  # noqa: F401 — re-exported for monkeypatch seam
    attempt_silent_relogin,
    configure_upstream_deps,
    make_3hk_request,
)

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class _MainDeps:
    """Adapter exposing main-module seam values to service and route modules.

    Each property reads the current value from ``main`` globals so that
    ``monkeypatch.setattr(main, 'session_store', fake)`` (and other seams)
    are immediately visible to session_utils, upstream, services, and routes.
    """

    @property
    def session_store(self) -> SessionStoreProtocol:  # noqa: F811
        return globals()["session_store"]

    @property
    def decrypt_password(self) -> Callable[[str | None], str | None]:  # noqa: F811
        return globals()["decrypt_password"]

    @property
    def get_isolated_session(self) -> Callable[[], requests.Session]:  # noqa: F811
        return globals()["get_isolated_session"]

    @property
    def _save_session(self) -> Callable[[SessionContext], None]:  # noqa: F811
        return globals()["_save_session"]

    @property
    def resolve_proxies(  # noqa: F811
        self,
    ) -> Callable[
        [str, MutableMapping[str, str] | None], MutableMapping[str, str] | None
    ]:
        return globals()["resolve_proxies"]

    @property
    def attempt_silent_relogin(  # noqa: F811
        self,
    ) -> Callable[[Request, SessionContext, str, dict[str, Any]], bool]:
        return globals()["attempt_silent_relogin"]

    @property
    def get_account_context(  # noqa: F811
        self,
    ) -> Callable[[SessionContext, str | None], dict[str, Any] | None]:
        return globals()["get_account_context"]

    @property
    def make_3hk_request(self) -> Callable[..., requests.Response | None]:  # noqa: F811
        return globals()["make_3hk_request"]

    @property
    def get_cache(self) -> Callable[[str], Any | None]:  # noqa: F811
        return globals()["get_cache"]

    @property
    def set_cache(self) -> Callable[..., None]:  # noqa: F811
        return globals()["set_cache"]

    @property
    def delete_cache(self) -> Callable[[str], None]:  # noqa: F811
        return globals()["delete_cache"]

    @property
    def notify(self) -> Callable[[str], None]:  # noqa: F811
        return globals()["notify"]

    @property
    def plans_refreshing(self) -> set[str]:  # noqa: F811
        return globals()["plans_refreshing"]

    @property
    def verify_auth_code(self) -> Callable[[Any, bool], tuple[bool, str]]:  # noqa: F811
        return globals()["verify_auth_code"]

    @property
    def _json_success(self) -> Callable[..., Any]:  # noqa: F811
        return globals()["_json_success"]

    @property
    def _json_error(self) -> Callable[..., Any]:  # noqa: F811
        return globals()["_json_error"]

    @property
    def _upstream_error(self) -> Callable[..., Any]:  # noqa: F811
        return globals()["_upstream_error"]

    @property
    def _create_session(self) -> Callable[[], SessionContext]:  # noqa: F811
        return globals()["_create_session"]

    @property
    def encrypt_password(self) -> Callable[[str | None], str | None]:  # noqa: F811
        return globals()["encrypt_password"]

    @property
    def _require_login(self) -> Callable[[Request], SessionContext | None]:  # noqa: F811
        return globals()["_require_login"]

    @property
    def get_brand_by_sub_id(  # noqa: F811
        self,
    ) -> Callable[[SessionContext, str | None, str | None], str]:
        return globals()["get_brand_by_sub_id"]

    @property
    def fetch_and_save_plans_background(self) -> Callable[..., None]:  # noqa: F811
        return globals()["fetch_and_save_plans_background"]

    @property
    def _redirect_to_login(self) -> Callable[..., Any]:  # noqa: F811
        return globals()["_redirect_to_login"]

    @property
    def _validate_csrf(self) -> Callable[..., Any]:  # noqa: F811
        return globals()["_validate_csrf"]

    @property
    def handle_purchase_event(self) -> Callable[..., None]:  # noqa: F811
        return globals()["handle_purchase_event"]

    @property
    def internal_logout_account(  # noqa: F811
        self,
    ) -> Callable[[SessionContext, str], bool]:
        return globals()["internal_logout_account"]

    @property
    def _mark_session_cookie_for_deletion(  # noqa: F811
        self,
    ) -> Callable[[Request], None]:
        return globals()["_mark_session_cookie_for_deletion"]

    @property
    def _clear_session(self) -> Callable[[SessionContext], None]:  # noqa: F811
        return globals()["_clear_session"]


    @property
    def BASE_HEADERS(self) -> MutableMapping[str, str]:  # noqa: F811
        return globals()["BASE_HEADERS"]

    @property
    def PROXIES(self) -> MutableMapping[str, str] | None:  # noqa: F811
        return globals()["PROXIES"]

    @property
    def SUB_BRANDS(self) -> Sequence[str]:  # noqa: F811
        return globals()["SUB_BRANDS"]

    @property
    def FRONTEND_DIST_DIR(self) -> Path:  # noqa: F811
        return globals()["FRONTEND_DIST_DIR"]

    @property
    def PLANS_CACHE_DIR(self) -> Path:  # noqa: F811
        return globals()["PLANS_CACHE_DIR"]

    @property
    def SESSION_SECRET(self) -> str:  # noqa: F811
        return globals()["SESSION_SECRET"]

    @property
    def redis_client(self) -> redis.Redis:  # noqa: F811
        return globals()["redis_client"]


_main_deps = _MainDeps()


def _live_session_store() -> SessionStoreProtocol:
    return globals()["session_store"]


configure_session_store(_live_session_store)
configure_upstream_deps(lambda: _main_deps)
configure_service_deps(lambda: _main_deps)


def internal_logout_account(ctx: SessionContext, account_id: str) -> bool:
    accounts = ctx.data.get("accounts", {})
    if isinstance(accounts, dict) and account_id in accounts:
        del accounts[account_id]
    delete_cache(f"profile_{account_id}")

    if not accounts:
        _clear_session(ctx)
        return False

    ctx.data["accounts"] = accounts
    _save_session(ctx)
    return True


@asynccontextmanager
async def lifespan(_: FastAPI):
    auth_code_store.seed_from_file()
    logger.info("3HK New App started")
    yield


def create_app() -> FastAPI:
    app = FastAPI(
        title="3HK New Native FastAPI App",
        description="FastAPI 原生后端实现，完整兼容既有接口行为。",
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(SessionMiddleware)

    if FRONTEND_STATIC_DIR.exists():
        app.mount("/static", StaticFiles(directory=FRONTEND_STATIC_DIR), name="static")
    app.mount(
        "/assets", StaticFiles(directory=FRONTEND_DIST_DIR / "assets"), name="assets"
    )

    deps = _main_deps
    register_system_routes(app, deps)
    register_auth_routes(app, deps)
    register_account_page_routes(app, deps)
    register_profile_routes(app, deps)
    register_commerce_routes(app, deps)
    register_cmn_routes(app, deps)
    register_transfer_routes(app, deps)
    register_messages_routes(app, deps)
    register_session_routes(app, deps)

    return app


application = create_app()
app = application
