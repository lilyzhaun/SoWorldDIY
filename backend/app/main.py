from __future__ import annotations

import json
import logging
import threading
import time
from collections.abc import Callable, MutableMapping
from contextlib import asynccontextmanager
from typing import Any, TypedDict

import requests
from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from redis.exceptions import RedisError
from starlette.responses import Response

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
from .runtime import (
    BASE_HEADERS,
    FRONTEND_DIST_DIR,
    FRONTEND_STATIC_DIR,
    PLANS_CACHE_DIR,
    PROXIES,
    SESSION_SECRET,
    SUB_BRANDS,
    auth_code_store,
    decrypt_password,  # noqa: F401 — re-exported for monkeypatch seam
    delete_cache,  # noqa: F401 — re-exported for monkeypatch seam
    encrypt_password,  # noqa: F401 — re-exported for monkeypatch seam
    get_cache,  # noqa: F401 — re-exported for monkeypatch seam
    get_isolated_session,  # noqa: F401 — re-exported for monkeypatch seam
    plans_refresh_lock,  # noqa: F401 — re-exported for monkeypatch seam
    plans_refreshing,  # noqa: F401 — re-exported for monkeypatch seam
    redis_client,
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
    """Adapter exposing main-module seam values to service modules.

    Each property reads the current value from ``main`` globals so that
    ``monkeypatch.setattr(main, 'session_store', fake)`` (and other seams)
    are immediately visible to session_utils, upstream, and services.
    """

    @property
    def session_store(self) -> SessionStoreProtocol:  # noqa: F811
        return globals()["session_store"]

    @property
    def decrypt_password(self) -> Callable[[str | None], str | None]:  # noqa: F811
        return globals()["decrypt_password"]

    @property
    def get_isolated_session(self) -> Callable[[], requests.Session]:
        return globals()["get_isolated_session"]

    @property
    def _save_session(self) -> Callable[[SessionContext], None]:
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
    def get_account_context(
        self,
    ) -> Callable[[SessionContext, str | None], dict[str, Any] | None]:
        return globals()["get_account_context"]

    @property
    def make_3hk_request(self) -> Callable[..., requests.Response | None]:
        return globals()["make_3hk_request"]

    @property
    def get_cache(self) -> Callable[[str], Any | None]:
        return globals()["get_cache"]

    @property
    def notify(self) -> Callable[[str], None]:
        return globals()["notify"]

    @property
    def plans_refreshing(self) -> set[str]:  # noqa: F811
        return globals()["plans_refreshing"]


_main_deps = _MainDeps()


def _live_session_store() -> SessionStoreProtocol:
    return globals()["session_store"]


configure_session_store(_live_session_store)
configure_upstream_deps(lambda: _main_deps)
configure_service_deps(lambda: _main_deps)


class DTOAgg(TypedDict):
    usages: list[dict[str, Any]]
    dates: list[str]
    is_vowifi: bool


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

    @app.get("/_health")
    async def healthcheck() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/_ready")
    async def readiness() -> JSONResponse:
        checks: dict[str, bool] = {
            "redis": False,
            "frontend_index": (FRONTEND_DIST_DIR / "index.html").exists(),
            "frontend_login": (FRONTEND_DIST_DIR / "login.html").exists(),
            "frontend_assets": (FRONTEND_DIST_DIR / "assets").exists(),
            "frontend_manifest": (FRONTEND_DIST_DIR / "manifest.json").exists(),
            "frontend_sw": (FRONTEND_DIST_DIR / "sw.js").exists(),
            "plans_cache_dir": PLANS_CACHE_DIR.exists(),
        }
        try:
            checks["redis"] = bool(redis_client.ping())
        except RedisError:
            checks["redis"] = False
        status_code = 200 if all(checks.values()) else 503
        return JSONResponse(
            status_code=status_code,
            content={
                "status": "ok" if status_code == 200 else "error",
                "checks": checks,
            },
        )

    @app.get("/manifest.json")
    async def manifest() -> FileResponse:
        return FileResponse(
            FRONTEND_DIST_DIR / "manifest.json", media_type="application/manifest+json"
        )

    @app.get("/sw.js")
    async def service_worker() -> FileResponse:
        return FileResponse(
            FRONTEND_DIST_DIR / "sw.js", media_type="application/javascript"
        )

    @app.get("/")
    async def index(request: Request) -> Response:
        ctx = getattr(request.state, "session_ctx", None)
        if request.query_params.get("add") == "1":
            return FileResponse(
                FRONTEND_DIST_DIR / "login.html", media_type="text/html"
            )

        accounts = ctx.data.get("accounts", {}) if ctx else {}
        if isinstance(accounts, dict) and accounts:
            first_id = list(accounts.keys())[0]
            return RedirectResponse(url=f"/main/{first_id}", status_code=302)
        return FileResponse(FRONTEND_DIST_DIR / "login.html", media_type="text/html")

    @app.post("/api/check-user")
    async def check_user(request: Request) -> JSONResponse:
        data = await request.json()
        try:
            identifier = str(data["identifier"])
            headers = dict(BASE_HEADERS)
            headers["User-Agent"] = request.headers.get("User-Agent", "Mozilla/5.0")
            with get_isolated_session() as s:
                r = s.post(
                    "https://www.three.com.hk/account-pro/user/existingCustDipping",
                    json={"id": identifier},
                    headers=headers,
                    proxies=PROXIES,
                    timeout=10,
                )
                if r.status_code == 200:
                    return _json_success(
                        {
                            "status": "success",
                            "subBrand": r.json().get("subBrand", "THREE"),
                        }
                    )
                return JSONResponse(status_code=400, content={"status": "error"})
        except Exception as exc:
            return JSONResponse(
                status_code=500, content={"status": "error", "message": str(exc)}
            )

    @app.post("/api/send-otp")
    async def send_otp(request: Request) -> JSONResponse:
        data = await request.json()
        valid, message = verify_auth_code(data.get("auth_code"), False)
        if not valid:
            return _json_error(message, 400)

        ident = str(data.get("identifier", ""))
        sub_brand = "THREE"
        headers = dict(BASE_HEADERS)
        headers["User-Agent"] = request.headers.get("User-Agent", "Mozilla/5.0")

        try:
            with get_isolated_session() as s:
                r = s.post(
                    "https://www.three.com.hk/account-pro/user/existingCustDipping",
                    json={"id": ident},
                    headers=headers,
                    proxies=PROXIES,
                    timeout=5,
                )
                sub_brand = r.json().get("subBrand", "THREE")
        except Exception:
            pass

        try:
            with get_isolated_session() as s:
                r = s.post(
                    f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{sub_brand}/user/requestLoginOtp",
                    json={"id": ident, "lang": "tc"},
                    headers=headers,
                    proxies=PROXIES,
                    timeout=10,
                )
                if r.status_code in [200, 204]:
                    return _json_success({"status": "success"})
                return _upstream_error(r, "验证码发送失败，请稍后重试", 400)
        except Exception as exc:
            return JSONResponse(
                status_code=500, content={"status": "error", "message": str(exc)}
            )

    @app.post("/login")
    async def handle_login(request: Request) -> JSONResponse:
        ctx = getattr(request.state, "session_ctx", None)
        form = await request.form()
        login_type = str(form.get("login_type", ""))
        identifier = str(form.get("identifier", ""))
        auth_code = str(form.get("auth_code", ""))
        password_raw = form.get("password")
        otp_raw = form.get("otp")
        password = str(password_raw) if password_raw is not None else None
        otp = str(otp_raw) if otp_raw is not None else None

        valid, message = verify_auth_code(auth_code, True)
        if not valid:
            return _json_error(message, 400)

        sub_brand = "THREE"
        headers = dict(BASE_HEADERS)
        headers["User-Agent"] = request.headers.get("User-Agent", "Mozilla/5.0")
        try:
            with get_isolated_session() as s:
                r_check = s.post(
                    "https://www.three.com.hk/account-pro/user/existingCustDipping",
                    json={"id": identifier},
                    headers=headers,
                    proxies=PROXIES,
                    timeout=10,
                )
                if r_check.status_code == 200:
                    sub_brand = r_check.json().get("subBrand", "THREE")
                else:
                    return _json_error("账号无效或网络错误", 400)
        except Exception as exc:
            return _json_error(f"账号检查失败: {exc}", 500)

        if login_type == "password":
            login_url = (
                "https://simworld.net/SIMworldApi-pro/HTHK/THREE/THREE/user/login/"
            )
            sub_brand = "THREE"
        else:
            login_url = f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{sub_brand}/user/login"

        payload: dict[str, Any] = {"id": identifier}
        if login_type == "password":
            payload["password"] = password
            payload["rememberMe"] = True
        else:
            payload["otp"] = otp
            payload["rememberMe"] = "true"

        try:
            with get_isolated_session() as s:
                r = s.post(
                    login_url,
                    json=payload,
                    headers=headers,
                    proxies=PROXIES,
                    timeout=10,
                )
                if r.status_code == 204:
                    try:
                        if ctx is None:
                            ctx = _create_session()
                            request.state.session_ctx = ctx
                            request.state.delete_session_cookie = False
                    except RuntimeError as exc:
                        return _json_error(str(exc), 503)
                    cookies = requests.utils.dict_from_cookiejar(r.cookies)
                    credential = password if login_type == "password" else f"OTP: {otp}"
                    accounts = ctx.data.get("accounts", {})
                    accounts[str(identifier)] = {
                        "cookies": cookies,
                        "sub_brand": sub_brand,
                        "auth_code": auth_code,
                        "credential": credential,
                        "login_type": login_type,
                        "stored_password_encrypted": encrypt_password(password)
                        if login_type == "password"
                        else None,
                    }
                    ctx.data["accounts"] = accounts
                    ctx.data["last_session_refresh"] = time.time()
                    try:
                        _save_session(ctx)
                    except RuntimeError as exc:
                        return _json_error(str(exc), 503)

                    try:
                        _save_session(ctx)
                    except RuntimeError as exc:
                        return _json_error(str(exc), 503)

                    try:
                        notify(
                            f"🚀 新用户登录\n账号: {identifier}\n模式: {login_type}\n品牌: {sub_brand}\n当前共 {len(accounts)} 个账号",
                        )
                    except Exception:
                        pass

                    return _json_success(
                        {"status": "success", "redirect": f"/main/{identifier}"}
                    )

            return _json_error("登录失败，请检查密码或OTP", 401)
        except Exception as exc:
            return _json_error(str(exc), 500)

    @app.get("/main")
    async def main_page_default(request: Request) -> RedirectResponse:
        ctx = _require_login(request)
        if not ctx:
            return RedirectResponse(url="/", status_code=302)
        accounts = ctx.data.get("accounts", {})
        first_id = list(accounts.keys())[0]
        return RedirectResponse(url=f"/main/{first_id}", status_code=302)

    @app.get("/main/{account_id}")
    async def main_page(request: Request, account_id: str) -> Response:
        ctx = _require_login(request)
        if not ctx:
            return RedirectResponse(url="/", status_code=302)

        accounts = ctx.data.get("accounts", {})
        if account_id not in accounts:
            return RedirectResponse(url="/", status_code=302)
        return FileResponse(FRONTEND_DIST_DIR / "index.html", media_type="text/html")

    @app.get("/api/profile")
    async def get_profile_api(request: Request) -> Response:
        ctx = _require_login(request)
        if not ctx:
            return RedirectResponse(url="/", status_code=302)

        req_ident = request.query_params.get("account_id")
        if not req_ident:
            return _json_error("Missing account_id", 400)

        account_ctx = get_account_context(ctx, req_ident)
        if not account_ctx:
            return _json_error("Invalid account", 401)

        if request.query_params.get("refresh") == "true":
            delete_cache(f"profile_{req_ident}")

        cached = get_cache(f"profile_{req_ident}")
        if cached:
            return _json_success(cached)

        available_accounts: list[dict[str, Any]] = []
        for key, val in ctx.data.get("accounts", {}).items():
            available_accounts.append(
                {
                    "identifier": key,
                    "active": str(key) == str(req_ident),
                    "subBrand": val.get("sub_brand", "THREE"),
                }
            )

        agg: dict[str, dict[str, Any]] = {}
        user_email = ""

        def safe_date_str(val: Any) -> str:
            if val and isinstance(val, str) and "T" in val:
                return val.split("T")[0]
            return ""

        def fuzzy_time_key(val: Any) -> Any:
            if val and isinstance(val, str) and len(val) >= 16:
                return val[:16]
            return val

        for brand in SUB_BRANDS:
            try:
                r = make_3hk_request(
                    request=request,
                    ctx=ctx,
                    method="GET",
                    url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{brand}/user/getProfile",
                    account_id=req_ident,
                    account_context=account_ctx,
                )
                if r and r.status_code == 200:
                    data = r.json()
                    if not user_email and data.get("email"):
                        user_email = data.get("email", "")
                    subscriptions = data.get("subscriptions", [])
                    for sub in subscriptions:
                        mobile = sub.get("primaryMsisdn")
                        if not mobile or mobile in agg:
                            continue

                        raw_offers = sub.get("subscriptionOffers", [])
                        dto_sender_map: dict[Any, Any] = {}
                        for offer in raw_offers:
                            if offer.get("offerSubType") == "DTO":
                                sender = offer.get("transferFromMsisdn")
                                end_date = offer.get("endDate")
                                if sender and end_date:
                                    dto_sender_map[fuzzy_time_key(end_date)] = sender

                        active_offers: list[dict[str, Any]] = []
                        dto_voice_agg: DTOAgg = {
                            "usages": [],
                            "dates": [],
                            "is_vowifi": False,
                        }
                        dto_data_agg: DTOAgg = {
                            "usages": [],
                            "dates": [],
                            "is_vowifi": False,
                        }

                        for offer in raw_offers:
                            if offer.get("planStatus") not in ["ACTIVE", "PREACTIVE"]:
                                continue
                            offer_type = offer.get("offerType")
                            sub_type = offer.get("offerSubType")
                            is_dto = sub_type == "DTO"
                            is_vas = offer_type == "VAS"
                            if not (is_vas or is_dto):
                                continue

                            is_vowifi = False
                            raw_products = offer.get("subscriptionProducts", [])
                            for prod in raw_products:
                                if "VOWIFI" in str(
                                    prod.get("productName", "")
                                ).upper().replace(" ", ""):
                                    is_vowifi = True
                                    break

                            current_offer_id = offer.get("offerId")
                            offer_transfer = offer.get("transferAllowed", False)
                            usage_list: list[dict[str, Any]] = []

                            for prod in raw_products:
                                prod_transfer = prod.get("transferAllowed", False)
                                min_quota = prod.get("minTransferQuota", 0)
                                spec_type = str(prod.get("productSpecType", "")).upper()
                                if "VOICE" in spec_type:
                                    p_family = "VOICE"
                                elif "DATA" in spec_type:
                                    p_family = "DATA"
                                else:
                                    p_family = prod.get("productFamily", "DATA")

                                for bal in prod.get("matrixxBalanceInfos", []):
                                    if bal.get("unit") in ["Money", "HKD"]:
                                        continue
                                    total = float(bal.get("grantAmount", 0))
                                    remain = float(bal.get("amount", 0))
                                    if total > 0 or remain > 0:
                                        usage_list.append(
                                            {
                                                "name": prod.get("productName"),
                                                "unit": bal.get("unit"),
                                                "total": total,
                                                "remain": remain,
                                                "percent": (remain / total * 100)
                                                if total > 0
                                                else 0,
                                                "canTransfer": offer_transfer
                                                or prod_transfer,
                                                "minTransfer": min_quota,
                                                "balanceResourceId": bal.get(
                                                    "resourceId",
                                                    bal.get("balanceResourceId"),
                                                ),
                                                "productFamily": p_family,
                                                "userOfferId": current_offer_id,
                                            }
                                        )

                            if is_dto:
                                if usage_list:
                                    end_date_raw = offer.get("endDate", "")
                                    end_date_str = safe_date_str(end_date_raw)
                                    sender = offer.get(
                                        "transferFromMsisdn"
                                    ) or dto_sender_map.get(
                                        fuzzy_time_key(end_date_raw),
                                        "未知好友",
                                    )
                                    formatted_name = f"來自{sender} {end_date_str}結束"
                                    for usage in usage_list:
                                        usage["name"] = formatted_name
                                        target_agg = (
                                            dto_voice_agg
                                            if usage["productFamily"] == "VOICE"
                                            else dto_data_agg
                                        )
                                        target_agg["usages"].append(usage)
                                        if end_date_str:
                                            target_agg["dates"].append(end_date_str)
                                        if is_vowifi:
                                            target_agg["is_vowifi"] = True
                            else:
                                if usage_list or is_vas:
                                    active_offers.append(
                                        {
                                            "offerId": current_offer_id,
                                            "name": offer.get(
                                                "offerNameChi", offer.get("offerName")
                                            ),
                                            "desc": offer.get(
                                                "offerDescChi", offer.get("offerDesc")
                                            ),
                                            "price": offer.get("offerPrice", 0),
                                            "endDate": safe_date_str(
                                                offer.get("endDate")
                                            ),
                                            "isVoWifi": is_vowifi,
                                            "planStatus": offer.get("planStatus"),
                                            "usage": usage_list,
                                        }
                                    )

                        if dto_voice_agg["usages"]:
                            active_offers.append(
                                {
                                    "offerId": "DTO_VOICE_AGG",
                                    "name": "轉入的分鐘",
                                    "desc": "來自好友互傳的語音資源聚合",
                                    "price": 0,
                                    "endDate": max(dto_voice_agg["dates"])
                                    if dto_voice_agg["dates"]
                                    else "",
                                    "isVoWifi": dto_voice_agg["is_vowifi"],
                                    "planStatus": "ACTIVE",
                                    "usage": dto_voice_agg["usages"],
                                }
                            )
                        if dto_data_agg["usages"]:
                            active_offers.append(
                                {
                                    "offerId": "DTO_DATA_AGG",
                                    "name": "轉入的數據",
                                    "desc": "來自好友互傳的上網數據聚合",
                                    "price": 0,
                                    "endDate": max(dto_data_agg["dates"])
                                    if dto_data_agg["dates"]
                                    else "",
                                    "isVoWifi": dto_data_agg["is_vowifi"],
                                    "planStatus": "ACTIVE",
                                    "usage": dto_data_agg["usages"],
                                }
                            )

                        agg[mobile] = {
                            "mobile": mobile,
                            "activationDate": safe_date_str(sub.get("activationDate")),
                            "subsEndDate": safe_date_str(sub.get("subsEndDate")),
                            "subscriptionId": sub.get("subscriptionId"),
                            "brand": brand,
                            "iccid": sub.get("iccid", ""),
                            "status": sub.get("status", ""),
                            "activeOffers": active_offers,
                        }
            except Exception as exc:
                logger.error("Err parsing %s: %s", brand, exc)
                continue

        subscriptions_list = list(agg.values())
        result = {
            "status": "success",
            "data": {
                "email": user_email,
                "subscriptions": subscriptions_list,
                "current": subscriptions_list[0] if subscriptions_list else {},
                "available_accounts": available_accounts,
            },
        }
        if subscriptions_list:
            set_cache(f"profile_{req_ident}", result)
        return _json_success(result)

    @app.get("/api/plans")
    async def get_plans_api(request: Request) -> Response:
        ctx = _require_login(request)
        if not ctx:
            return RedirectResponse(url="/", status_code=302)

        req_ident = request.query_params.get("account_id")
        account_ctx = get_account_context(ctx, req_ident)
        if not account_ctx:
            return JSONResponse(status_code=401, content={"status": "error"})

        sub_id = request.query_params.get("subscriptionId")
        brand_override = request.query_params.get("brand")
        target_brand = (
            brand_override
            if brand_override
            else get_brand_by_sub_id(ctx, sub_id, req_ident)
        )

        cache_file = PLANS_CACHE_DIR / f"plans_{target_brand}.json"
        curr_cookies = account_ctx.get("cookies", {})
        curr_ua = request.headers.get("User-Agent")

        if cache_file.exists():
            try:
                cached_data = json.loads(cache_file.read_text(encoding="utf-8"))
                threading.Thread(
                    target=fetch_and_save_plans_background,
                    args=(target_brand, curr_cookies, curr_ua),
                ).start()
                return _json_success(cached_data)
            except Exception:
                pass

        fetch_and_save_plans_background(target_brand, curr_cookies, curr_ua)
        if cache_file.exists():
            return _json_success(json.loads(cache_file.read_text(encoding="utf-8")))
        return _json_error("Fetch plans failed", 400)

    @app.get("/api/balance")
    async def get_balance(request: Request) -> Response:
        ctx = _require_login(request)
        if not ctx:
            return _redirect_to_login()

        req_ident = request.query_params.get("account_id")
        account_ctx = get_account_context(ctx, req_ident)
        if not account_ctx:
            return _json_success({"status": "success", "balance": 0})

        sid = request.query_params.get("subscriptionId")
        target_brand = get_brand_by_sub_id(ctx, sid, req_ident)
        try:
            r = make_3hk_request(
                request=request,
                ctx=ctx,
                method="GET",
                url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{target_brand}/sim/{sid}/WalletBalances",
                account_id=req_ident,
                account_context=account_ctx,
            )
            data = r.json() if r and r.status_code == 200 else []
            balance = (
                max(float(item.get("amount", 0)) for item in data if "amount" in item)
                if isinstance(data, list) and data
                else 0
            )
            return _json_success({"status": "success", "balance": balance})
        except Exception:
            return _json_success({"status": "success", "balance": 0})

    @app.post("/api/purchase")
    async def purchase_plan(request: Request) -> Response:
        ctx = _require_login(request)
        if not ctx:
            return _redirect_to_login()
        csrf_error = _validate_csrf(request, ctx)
        if csrf_error:
            return csrf_error

        data = await request.json()
        req_ident = data.get("account_id") or request.query_params.get("account_id")
        account_ctx = get_account_context(
            ctx, str(req_ident) if req_ident is not None else None
        )
        if not account_ctx:
            return _json_error("Auth failed", 401)

        sid = data.get("subscriptionId")
        new_line = bool(data.get("new_line", False))
        target_brand = get_brand_by_sub_id(ctx, str(sid), str(req_ident))
        try:
            kr = make_3hk_request(
                request=request,
                ctx=ctx,
                method="GET",
                url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{target_brand}/pmt/accessPurchaseKey",
                account_id=str(req_ident),
                account_context=account_ctx,
            )
            if not kr:
                return _json_error("Request failed", 400)
            access_key = kr.json().get("accessPurchaseKey")
            txn = float(data.get("txnAmount", 0))
            pmt: dict[str, Any] = {"amnt": max(0.0, float(data.get("price", 0)) - txn)}
            if pmt["amnt"] > 0:
                pmt.update({"lang": "tc", "type": data.get("paymentType", "ALCN")})

            if new_line:
                offers_payload = [
                    {
                        "offerId": "H3OF00000000001",
                        "quantity": 1,
                        "autoRenewFlag": False,
                    },
                ]
                for item in data.get("items", []):
                    if item.get("offerId") != "H3OF00000000001":
                        offers_payload.append(
                            {
                                "offerId": item["offerId"],
                                "quantity": int(item["quantity"]),
                                "autoRenewFlag": False,
                            }
                        )
                payload = {
                    "fUrl": "https://www.three.com.hk/prepaid/DIY/tc/checkout/payment/finished?actionflow=NEWSIM&purchaseid={purchaseid}",
                    "accessPurchaseKey": access_key,
                    "purchaseType": "PREPAID_DIY",
                    "order": {
                        "channel": "GLOBAL_ESIM",
                        "autoPayFlag": False,
                        "pmt": pmt,
                        "orderSubscription": {
                            "lang": "tc",
                            "offers": offers_payload,
                            "promoOptOuts": [],
                            "simType": "ESIM",
                        },
                    },
                }
            else:
                offers_payload = [
                    {
                        "offerId": item["offerId"],
                        "quantity": int(item["quantity"]),
                        "autoRenewFlag": False,
                    }
                    for item in data.get("items", [])
                ]
                sub_payload: dict[str, Any] = {
                    "lang": "tc",
                    "subscriptionId": sid,
                    "offers": offers_payload,
                }
                if txn > 0:
                    sub_payload["walletPayment"] = {"txnAmount": txn}
                payload = {
                    "fUrl": "https://simworld.net/SIMworld/main/tc",
                    "purchaseType": "SOSIM_VAS",
                    "accessPurchaseKey": access_key,
                    "order": {
                        "channel": "ONLINE",
                        "autoPayFlag": False,
                        "lang": "tc",
                        "pmt": pmt,
                        "orderSubscriptions": [sub_payload],
                    },
                }
            r = make_3hk_request(
                request=request,
                ctx=ctx,
                method="POST",
                url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{target_brand}/pmt/purchase/createPurchase/",
                json_data=payload,
                account_id=str(req_ident),
                account_context=account_ctx,
            )
            if r and r.status_code == 200 and "paymentUrl" in r.json():
                delete_cache(f"profile_{req_ident}")
                handle_purchase_event(
                    r.json()["paymentUrl"], str(sid), pmt["amnt"], str(req_ident)
                )
                return _json_success(
                    {"status": "success", "paymentUrl": r.json()["paymentUrl"]}
                )
            return _upstream_error(r, "购买请求失败，请稍后重试", 400)
        except Exception as exc:
            return _json_error(str(exc), 500)

    @app.get("/api/cmn/check")
    async def check_cmn(request: Request) -> Response:
        ctx = _require_login(request)
        if not ctx:
            return _redirect_to_login()

        req_ident = request.query_params.get("account_id")
        account_ctx = get_account_context(ctx, req_ident)
        if not account_ctx:
            return _redirect_to_login()

        sid = request.query_params.get("subscriptionId")
        target_brand = get_brand_by_sub_id(ctx, sid, req_ident)
        r = make_3hk_request(
            request=request,
            ctx=ctx,
            method="GET",
            url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{target_brand}/offer/getCmnOffer",
            account_id=req_ident,
            account_context=account_ctx,
        )
        offers = r.json().get("offers", []) if r and r.status_code == 200 else []
        if not offers:
            return _json_error("无资格", 400)
        offer = offers[0]
        return _json_success(
            {
                "status": "success",
                "data": {
                    "offerId": offer["offerId"],
                    "offerSubType": offer["offerSubType"],
                    "price": offer["offerPrice"],
                    "name": offer["offerNameChi"],
                },
            }
        )

    @app.api_route("/api/cmn/numbers", methods=["GET", "POST"])
    async def get_cmn_numbers(request: Request) -> Response:
        ctx = _require_login(request)
        if not ctx:
            return _redirect_to_login()
        if request.method == "POST":
            csrf_error = _validate_csrf(request, ctx)
            if csrf_error:
                return csrf_error

        if request.method == "GET":
            req_ident = request.query_params.get("account_id")
            sid = request.query_params.get("subscriptionId")
        else:
            form = await request.form()
            req_ident = str(form.get("account_id")) if form.get("account_id") else None
            sid = (
                str(form.get("subscriptionId")) if form.get("subscriptionId") else None
            )

        account_ctx = get_account_context(ctx, req_ident)
        if not account_ctx:
            return _redirect_to_login()

        target_brand = get_brand_by_sub_id(ctx, sid, req_ident)
        r = make_3hk_request(
            request=request,
            ctx=ctx,
            method="POST",
            url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{target_brand}/mnms/holdAvailableNumbersFor15m/10/",
            account_id=req_ident,
            account_context=account_ctx,
        )
        if not r or r.status_code != 200:
            return _json_error("Fetch failed", 400)
        numbers = sorted(list(set(r.json().get("lineList", []))))
        return _json_success({"status": "success", "numbers": numbers})

    @app.post("/api/cmn/purchase")
    async def purchase_cmn(request: Request) -> Response:
        ctx = _require_login(request)
        if not ctx:
            return _redirect_to_login()
        csrf_error = _validate_csrf(request, ctx)
        if csrf_error:
            return csrf_error

        data = await request.json()
        req_ident = str(data.get("account_id", ""))
        account_ctx = get_account_context(ctx, req_ident)
        if not account_ctx:
            return _redirect_to_login()

        sid = data.get("subscriptionId")
        target_brand = get_brand_by_sub_id(ctx, str(sid), req_ident)
        try:
            kr = make_3hk_request(
                request=request,
                ctx=ctx,
                method="GET",
                url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{target_brand}/pmt/accessPurchaseKey",
                account_id=req_ident,
                account_context=account_ctx,
            )
            if not kr:
                return _json_error("Request failed", 400)
            access_key = kr.json().get("accessPurchaseKey")
            txn = float(data.get("txnAmount", 0))
            pmt_amt = max(0.0, float(data.get("price", 0)) - txn)
            pmt: dict[str, Any] = {"amnt": pmt_amt}
            order_sub: dict[str, Any] = {
                "msisdn": str(data["selectedNumber"]),
                "lang": "tc",
                "subscriptionId": sid,
                "offers": [{"offerId": data["offerId"], "quantity": 1}],
            }
            if pmt_amt > 0:
                pmt.update({"lang": "tc", "type": data.get("paymentType", "ALCN")})
            if txn > 0:
                order_sub["walletPayment"] = {"txnAmount": txn}

            payload = {
                "fUrl": "https://simworld.net/SIMworld/main/checkout/payment/finished/",
                "purchaseType": "CMN_ONLY",
                "accessPurchaseKey": access_key,
                "order": {
                    "channel": "ONLINE",
                    "autoPayFlag": False,
                    "pmt": pmt,
                    "orderSubscription": order_sub,
                },
            }

            r = make_3hk_request(
                request=request,
                ctx=ctx,
                method="POST",
                url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{target_brand}/pmt/purchase/createPurchase/",
                json_data=payload,
                account_id=req_ident,
                account_context=account_ctx,
            )
            if r and r.status_code == 200 and "paymentUrl" in r.json():
                delete_cache(f"profile_{req_ident}")
                handle_purchase_event(
                    r.json()["paymentUrl"], str(sid), pmt_amt, req_ident
                )
                return _json_success(
                    {"status": "success", "paymentUrl": r.json()["paymentUrl"]}
                )
            return _upstream_error(r, "换号购买请求失败，请稍后重试", 400)
        except Exception as exc:
            return _json_error(str(exc), 500)

    @app.post("/api/sim/transfer")
    async def transfer_resource(request: Request) -> Response:
        ctx = _require_login(request)
        if not ctx:
            return _redirect_to_login()
        csrf_error = _validate_csrf(request, ctx)
        if csrf_error:
            return csrf_error

        data = await request.json()
        req_ident = str(data.get("account_id", ""))
        account_ctx = get_account_context(ctx, req_ident)
        if not account_ctx:
            return _redirect_to_login()

        sid = data.get("subscriptionId")
        target_brand = get_brand_by_sub_id(ctx, str(sid), req_ident)
        try:
            tr = make_3hk_request(
                request=request,
                ctx=ctx,
                method="GET",
                url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{target_brand}/offer/getTransferOffers",
                params={"subscriptionId": sid},
                account_id=req_ident,
                account_context=account_ctx,
            )
            if not tr:
                return _json_error("Request failed", 400)
            dto = next(
                (
                    o
                    for o in tr.json().get("offers", [])
                    if o.get("offerSubType") == "DTO"
                ),
                None,
            )
            if not dto:
                return _json_error("不支持转移", 400)

            target_product_id = next(
                (
                    p["productId"]
                    for p in dto.get("products", [])
                    if p.get("productFamily") == data.get("productFamily")
                ),
                dto["products"][0]["productId"],
            )
            payload = {
                "tranferOrder": {
                    "channel": "WEB",
                    "orderSubscription": {
                        "msisdn": str(data.get("sourceMsisdn")),
                        "subscriptionId": sid,
                        "volumeUpMsisdn": str(data.get("targetMsisdn")),
                        "lang": "tc",
                        "offers": [
                            {
                                "offerId": dto["offerId"],
                                "transferOfferId": data.get("userOfferId"),
                                "offerProduct": {
                                    "balanceResourceId": int(
                                        data.get("balanceResourceId")
                                    ),
                                    "productId": target_product_id,
                                    "productData": {
                                        "unit": data.get("unit"),
                                        "volume": float(data.get("amount")),
                                    },
                                },
                            }
                        ],
                    },
                }
            }

            r = make_3hk_request(
                request=request,
                ctx=ctx,
                method="POST",
                url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{target_brand}/sim/transferData",
                json_data=payload,
                account_id=req_ident,
                account_context=account_ctx,
            )
            if r and r.status_code == 200:
                delete_cache(f"profile_{req_ident}")
                return _json_success({"status": "success"})
            return _upstream_error(r, "资源转移请求失败，请稍后重试", 400)
        except Exception as exc:
            return _json_error(str(exc), 500)

    @app.get("/api/inbox")
    async def get_inbox(request: Request) -> Response:
        ctx = _require_login(request)
        if not ctx:
            return _redirect_to_login()

        req_ident = request.query_params.get("account_id")
        account_ctx = get_account_context(ctx, req_ident)
        if not account_ctx:
            return _redirect_to_login()

        messages: list[dict[str, Any]] = []
        seen: set[Any] = set()
        brand = account_ctx.get("sub_brand", "THREE")
        try:
            r = make_3hk_request(
                request=request,
                ctx=ctx,
                method="GET",
                url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{brand}/inbox/getMessages",
                params={"lang": "tc"},
                account_id=req_ident,
                account_context=account_ctx,
            )
            if r and r.status_code == 200:
                for msg in r.json().get("inbox_msgs", []):
                    msg_id = msg.get("msg_id")
                    if msg_id not in seen:
                        messages.append(msg)
                        seen.add(msg_id)
        except Exception:
            pass
        return _json_success(
            {
                "status": "success",
                "messages": sorted(
                    messages, key=lambda x: x.get("post_dt", ""), reverse=True
                ),
            }
        )

    @app.get("/api/history")
    async def get_transaction_history(request: Request) -> Response:
        ctx = _require_login(request)
        if not ctx:
            return _redirect_to_login()

        req_ident = request.query_params.get("account_id")
        account_ctx = get_account_context(ctx, req_ident)
        if not account_ctx:
            return _redirect_to_login()

        sid = request.query_params.get("subscriptionId")
        target_brand = get_brand_by_sub_id(ctx, sid, req_ident)
        params = {
            "type": "SUBSCRIPTION",
            "subscriptionId": sid,
            "startDate": request.query_params.get("startDate"),
            "endDate": request.query_params.get("endDate"),
        }
        try:
            r = make_3hk_request(
                request=request,
                ctx=ctx,
                method="GET",
                url=f"https://simworld.net/SIMworldApi-pro/HTHK/THREE/{target_brand}/pmt/TransactionHistory",
                params=params,
                account_id=req_ident,
                account_context=account_ctx,
            )
            if r and r.status_code == 200:
                return _json_success({"status": "success", "data": r.json()})
            return JSONResponse(status_code=400, content={"status": "error"})
        except Exception as exc:
            return _json_error(str(exc), 500)

    @app.get("/logout")
    async def logout(request: Request) -> RedirectResponse:
        ctx = getattr(request.state, "session_ctx", None)
        if ctx is None:
            _mark_session_cookie_for_deletion(request)
            return RedirectResponse(url="/", status_code=302)
        req_ident = request.query_params.get("account_id")
        if req_ident:
            try:
                has_left = internal_logout_account(ctx, req_ident)
            except RuntimeError:
                _mark_session_cookie_for_deletion(request)
                return RedirectResponse(url="/", status_code=302)
            if not has_left:
                _mark_session_cookie_for_deletion(request)
                return RedirectResponse(url="/", status_code=302)
            accounts = ctx.data.get("accounts", {})
            if accounts:
                first_id = list(accounts.keys())[0]
                return RedirectResponse(url=f"/main/{first_id}", status_code=302)

        try:
            _clear_session(ctx)
        except RuntimeError:
            pass
        _mark_session_cookie_for_deletion(request)
        return RedirectResponse(url="/", status_code=302)

    @app.post("/internal/session-cleanup")
    async def session_cleanup(request: Request) -> JSONResponse:
        provided_secret = request.headers.get("x-session-secret", "")
        if provided_secret != SESSION_SECRET:
            return _json_error("Unauthorized", 401)

        try:
            redis_ok = bool(redis_client.ping())
        except RedisError as exc:
            return _json_error(f"Redis unavailable: {exc}", 503)

        return _json_success({"redis_ok": redis_ok})

    return app


application = create_app()
app = application
