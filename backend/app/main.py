from __future__ import annotations

import logging
import sys
from contextlib import asynccontextmanager
from typing import cast

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from .main_deps import MainDepsAdapter, MainModuleSource
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
    TRUSTED_PROXY_IPS,  # noqa: F401 — re-exported for monkeypatch seam
    auth_code_store,
    decrypt_password,  # noqa: F401 — re-exported for monkeypatch seam
    delete_cache,  # noqa: F401 — re-exported for monkeypatch seam
    encrypt_password,  # noqa: F401 — re-exported for monkeypatch seam
    get_cache,  # noqa: F401 — re-exported for monkeypatch seam
    get_isolated_session,  # noqa: F401 — re-exported for monkeypatch seam
    plans_refresh_lock,  # noqa: F401 — re-exported for monkeypatch seam
    plans_refreshing,  # noqa: F401 — re-exported for monkeypatch seam
    rate_limiter,  # noqa: F401 — re-exported for monkeypatch seam
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


def _bind_main_deps(module: object) -> MainDepsAdapter:
    return MainDepsAdapter(source=cast(MainModuleSource, module))


_main_deps = _bind_main_deps(sys.modules[__name__])
_MainDeps = MainDepsAdapter


def _live_session_store() -> SessionStoreProtocol:
    return _main_deps.session_store


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
    if (FRONTEND_DIST_DIR / "assets").exists():
        app.mount(
            "/assets",
            StaticFiles(directory=FRONTEND_DIST_DIR / "assets"),
            name="assets",
        )

    # Reuse the module-level adapter; do not reconfigure global providers.
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
