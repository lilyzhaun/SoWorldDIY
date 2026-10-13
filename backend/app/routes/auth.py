from __future__ import annotations

import copy
import logging
import time
from typing import Any
from urllib.parse import quote

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from .. import runtime
from ..blocking import run_blocking
from ..cache_store import profile_cache_key
from ..public_errors import (
    ACCOUNT_CHECK_FAILED,
    CSRF_INVALID,
    INTERNAL_ERROR,
    INVALID_REQUEST,
    SERVICE_UNAVAILABLE,
)
from ..rate_limit_http import client_ip, guard
from ..responses import _public_error
from ..schemas import CheckUserRequest, SendOtpRequest
from ..security import new_csrf_token
from ..session_store import SessionConflictError
from ..upstream_urls import THREE_EXISTING_CUST_DIPPING, simworld_url
from .deps import RouteDeps

logger = logging.getLogger(__name__)


def register_auth_routes(app: FastAPI, deps: RouteDeps) -> None:
    @app.post("/api/check-user")
    async def check_user(request: Request) -> JSONResponse:
        ip = client_ip(request, deps.TRUSTED_PROXY_IPS)
        blocked = guard(
            await run_blocking(deps.rate_limiter.check_user_ip, ip),
            endpoint="check_user",
        )
        if blocked is not None:
            return blocked
        try:
            raw = await request.json()
        except ValueError:
            return _public_error(INVALID_REQUEST, 400)
        try:
            body = CheckUserRequest.model_validate(raw)
        except ValidationError:
            return _public_error(INVALID_REQUEST, 400)
        try:
            identifier = body.identifier
            headers = dict(deps.BASE_HEADERS)
            headers["User-Agent"] = request.headers.get("User-Agent", "Mozilla/5.0")
            with deps.get_isolated_session() as s:
                r = await run_blocking(
                    s.post,
                    THREE_EXISTING_CUST_DIPPING,
                    json={"id": identifier},
                    headers=headers,
                    proxies=deps.PROXIES,
                    timeout=10,
                )
                if r.status_code == 200:
                    return deps._json_success(
                        {
                            "status": "success",
                            "subBrand": r.json().get("subBrand", "THREE"),
                        }
                    )
                return JSONResponse(status_code=400, content={"status": "error"})
        except Exception as exc:
            logger.error("check_user failed error_class=%s", type(exc).__name__)
            return _public_error(INTERNAL_ERROR, 500)

    @app.post("/api/send-otp")
    async def send_otp(request: Request) -> JSONResponse:
        ip = client_ip(request, deps.TRUSTED_PROXY_IPS)
        blocked = guard(
            await run_blocking(deps.rate_limiter.send_otp_ip, ip), endpoint="send_otp"
        )
        if blocked is not None:
            return blocked
        try:
            raw = await request.json()
        except ValueError:
            return _public_error(INVALID_REQUEST, 400)
        try:
            body = SendOtpRequest.model_validate(raw)
        except ValidationError:
            return _public_error(INVALID_REQUEST, 400)

        valid, message = await run_blocking(
            deps.verify_auth_code, body.auth_code, False
        )
        if not valid:
            return deps._json_error(message, 400)

        blocked = guard(
            await run_blocking(deps.rate_limiter.send_otp_identifier, body.identifier),
            endpoint="send_otp",
        )
        if blocked is not None:
            return blocked

        ident = body.identifier
        sub_brand = "THREE"
        headers = dict(deps.BASE_HEADERS)
        headers["User-Agent"] = request.headers.get("User-Agent", "Mozilla/5.0")

        try:
            with deps.get_isolated_session() as s:
                r = await run_blocking(
                    s.post,
                    THREE_EXISTING_CUST_DIPPING,
                    json={"id": ident},
                    headers=headers,
                    proxies=deps.PROXIES,
                    timeout=5,
                )
                sub_brand = r.json().get("subBrand", "THREE")
        except Exception as exc:
            logger.warning(
                "send_otp brand lookup failed error_class=%s", type(exc).__name__
            )

        try:
            with deps.get_isolated_session() as s:
                r = await run_blocking(
                    s.post,
                    simworld_url(sub_brand, "user/requestLoginOtp"),
                    json={"id": ident, "lang": "tc"},
                    headers=headers,
                    proxies=deps.PROXIES,
                    timeout=10,
                )
                if r.status_code in [200, 204]:
                    return deps._json_success({"status": "success"})
                return deps._upstream_error(
                    r, "验证码发送失败，请稍后重试", 400, operation="send_otp"
                )
        except Exception as exc:
            logger.error(
                "send_otp failed error_class=%s brand=%s", type(exc).__name__, sub_brand
            )
            return _public_error(INTERNAL_ERROR, 500)

    @app.post("/login")
    async def handle_login(request: Request) -> JSONResponse:
        ip = client_ip(request, deps.TRUSTED_PROXY_IPS)
        blocked = guard(
            await run_blocking(deps.rate_limiter.login_ip, ip), endpoint="login"
        )
        if blocked is not None:
            return blocked
        ctx = getattr(request.state, "session_ctx", None)
        if ctx is None:
            return _public_error(CSRF_INVALID, 403)
        csrf_error = deps._validate_csrf(request, ctx)
        if csrf_error:
            return csrf_error
        expected_origin = f"{'https' if runtime.COOKIE_SECURE else request.url.scheme}://{request.url.netloc}"
        origin = request.headers.get("origin")
        if request.headers.get("sec-fetch-site") == "cross-site" or (
            origin is not None and origin.rstrip("/") != expected_origin
        ):
            return _public_error(CSRF_INVALID, 403)
        form = await request.form()
        login_type = str(form.get("login_type", ""))
        identifier = str(form.get("identifier", ""))
        auth_code = str(form.get("auth_code", ""))
        password_raw, otp_raw = form.get("password"), form.get("otp")
        password = str(password_raw) if password_raw is not None else None
        otp = str(otp_raw) if otp_raw is not None else None
        if (
            login_type not in {"password", "otp"}
            or not 1 <= len(identifier) <= 254
            or len(auth_code) > 512
            or (password is not None and len(password) > 1024)
            or (
                login_type == "otp"
                and (
                    otp is None
                    or not otp.isascii()
                    or not otp.isdigit()
                    or not 4 <= len(otp) <= 12
                )
            )
        ):
            return _public_error(INVALID_REQUEST, 400)

        blocked = guard(
            await run_blocking(
                deps.rate_limiter.peek_login_fail_identifier, identifier
            ),
            endpoint="login",
        )
        if blocked is not None:
            return blocked

        valid, message = await run_blocking(deps.verify_auth_code, auth_code, True)
        if not valid:
            return deps._json_error(message, 400)

        sub_brand = "THREE"
        headers = dict(deps.BASE_HEADERS)
        headers["User-Agent"] = request.headers.get("User-Agent", "Mozilla/5.0")
        try:
            with deps.get_isolated_session() as s:
                r_check = await run_blocking(
                    s.post,
                    THREE_EXISTING_CUST_DIPPING,
                    json={"id": identifier},
                    headers=headers,
                    proxies=deps.PROXIES,
                    timeout=10,
                )
                if r_check.status_code == 200:
                    sub_brand = r_check.json().get("subBrand", "THREE")
                else:
                    await run_blocking(
                        deps.rate_limiter.record_login_failure, identifier
                    )
                    return deps._json_error("账号无效或网络错误", 400)
        except Exception as exc:
            logger.error("login brand check failed error_class=%s", type(exc).__name__)
            return _public_error(ACCOUNT_CHECK_FAILED, 500)

        if login_type == "password":
            login_url = simworld_url("THREE", "user/login/")
            sub_brand = "THREE"
        else:
            login_url = simworld_url(sub_brand, "user/login")

        payload: dict[str, Any] = {"id": identifier}
        if login_type == "password":
            payload["password"] = password
            payload["rememberMe"] = True
        else:
            payload["otp"] = otp
            payload["rememberMe"] = "true"

        try:
            with deps.get_isolated_session() as s:
                r = await run_blocking(
                    s.post,
                    login_url,
                    json=payload,
                    headers=headers,
                    proxies=deps.PROXIES,
                    timeout=10,
                )
                if r.status_code == 204:
                    previous = copy.deepcopy(ctx.data)
                    cookies = requests.utils.dict_from_cookiejar(r.cookies)
                    accounts = ctx.data.get("accounts", {})
                    account_payload: dict[str, Any] = {
                        "cookies": cookies,
                        "sub_brand": sub_brand,
                        "login_type": login_type,
                    }
                    if login_type == "password":
                        account_payload["stored_password_encrypted"] = (
                            deps.encrypt_password(password)
                        )
                    accounts[str(identifier)] = account_payload
                    ctx.data["accounts"] = accounts
                    ctx.data["last_session_refresh"] = time.time()
                    ctx.data["csrf_token"] = new_csrf_token()
                    try:
                        rotated = await run_blocking(
                            deps.session_store.rotate, ctx.sid, ctx.data
                        )
                        request.state.session_ctx = rotated
                        request.state.delete_session_cookie = False
                    except SessionConflictError:
                        request.state.session_ctx = None
                        return JSONResponse(
                            status_code=409,
                            content={
                                "status": "error",
                                "code": "session_conflict",
                                "message": "会话已变更，请刷新或重新登录",
                            },
                        )
                    except RuntimeError as exc:
                        ctx.data = previous
                        logger.error(
                            "login save_session failed error_class=%s",
                            type(exc).__name__,
                        )
                        return _public_error(SERVICE_UNAVAILABLE, 503)

                    for account_id in accounts:
                        deps.delete_cache(profile_cache_key(ctx.sid, account_id))

                    await run_blocking(
                        deps.rate_limiter.clear_login_fail_identifier, identifier
                    )
                    return deps._json_success(
                        {
                            "status": "success",
                            "redirect": f"/main/{quote(identifier, safe='@')}",
                        }
                    )

            await run_blocking(deps.rate_limiter.record_login_failure, identifier)
            return deps._json_error("登录失败，请检查密码或OTP", 401)
        except Exception as exc:
            logger.error(
                "login failed error_class=%s login_type=%s",
                type(exc).__name__,
                login_type,
            )
            return _public_error(INTERNAL_ERROR, 500)
