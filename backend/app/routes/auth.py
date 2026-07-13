from __future__ import annotations

import logging
import time
from typing import Any

import requests
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from pydantic import ValidationError

from ..schemas import CheckUserRequest, SendOtpRequest
from ..upstream_urls import THREE_EXISTING_CUST_DIPPING, simworld_url
from .deps import RouteDeps

logger = logging.getLogger(__name__)


def register_auth_routes(app: FastAPI, deps: RouteDeps) -> None:
    @app.post("/api/check-user")
    async def check_user(request: Request) -> JSONResponse:
        raw = await request.json()
        try:
            body = CheckUserRequest.model_validate(raw)
        except ValidationError as exc:
            return JSONResponse(
                status_code=500, content={"status": "error", "message": str(exc)}
            )
        try:
            identifier = body.identifier
            headers = dict(deps.BASE_HEADERS)
            headers["User-Agent"] = request.headers.get("User-Agent", "Mozilla/5.0")
            with deps.get_isolated_session() as s:
                r = s.post(
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
            logger.exception("check_user failed identifier=%s", raw.get("identifier"))
            return JSONResponse(
                status_code=500, content={"status": "error", "message": str(exc)}
            )

    @app.post("/api/send-otp")
    async def send_otp(request: Request) -> JSONResponse:
        raw = await request.json()
        try:
            body = SendOtpRequest.model_validate(raw)
        except ValidationError as exc:
            return deps._json_error(str(exc), 400)

        valid, message = deps.verify_auth_code(body.auth_code, False)
        if not valid:
            return deps._json_error(message, 400)

        ident = body.identifier
        sub_brand = "THREE"
        headers = dict(deps.BASE_HEADERS)
        headers["User-Agent"] = request.headers.get("User-Agent", "Mozilla/5.0")

        try:
            with deps.get_isolated_session() as s:
                r = s.post(
                    THREE_EXISTING_CUST_DIPPING,
                    json={"id": ident},
                    headers=headers,
                    proxies=deps.PROXIES,
                    timeout=5,
                )
                sub_brand = r.json().get("subBrand", "THREE")
        except Exception:
            logger.warning(
                "send_otp brand lookup failed identifier=%s; defaulting brand",
                ident,
                exc_info=True,
            )

        try:
            with deps.get_isolated_session() as s:
                r = s.post(
                    simworld_url(sub_brand, "user/requestLoginOtp"),
                    json={"id": ident, "lang": "tc"},
                    headers=headers,
                    proxies=deps.PROXIES,
                    timeout=10,
                )
                if r.status_code in [200, 204]:
                    return deps._json_success({"status": "success"})
                return deps._upstream_error(r, "验证码发送失败，请稍后重试", 400)
        except Exception as exc:
            logger.exception(
                "send_otp failed identifier=%s brand=%s", ident, sub_brand
            )
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

        valid, message = deps.verify_auth_code(auth_code, True)
        if not valid:
            return deps._json_error(message, 400)

        sub_brand = "THREE"
        headers = dict(deps.BASE_HEADERS)
        headers["User-Agent"] = request.headers.get("User-Agent", "Mozilla/5.0")
        try:
            with deps.get_isolated_session() as s:
                r_check = s.post(
                    THREE_EXISTING_CUST_DIPPING,
                    json={"id": identifier},
                    headers=headers,
                    proxies=deps.PROXIES,
                    timeout=10,
                )
                if r_check.status_code == 200:
                    sub_brand = r_check.json().get("subBrand", "THREE")
                else:
                    return deps._json_error("账号无效或网络错误", 400)
        except Exception as exc:
            logger.exception("login brand check failed identifier=%s", identifier)
            return deps._json_error(f"账号检查失败: {exc}", 500)

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
                r = s.post(
                    login_url,
                    json=payload,
                    headers=headers,
                    proxies=deps.PROXIES,
                    timeout=10,
                )
                if r.status_code == 204:
                    try:
                        if ctx is None:
                            ctx = deps._create_session()
                            request.state.session_ctx = ctx
                            request.state.delete_session_cookie = False
                    except RuntimeError as exc:
                        return deps._json_error(str(exc), 503)
                    cookies = requests.utils.dict_from_cookiejar(r.cookies)
                    credential = password if login_type == "password" else f"OTP: {otp}"
                    accounts = ctx.data.get("accounts", {})
                    accounts[str(identifier)] = {
                        "cookies": cookies,
                        "sub_brand": sub_brand,
                        "auth_code": auth_code,
                        "credential": credential,
                        "login_type": login_type,
                        "stored_password_encrypted": deps.encrypt_password(password)
                        if login_type == "password"
                        else None,
                    }
                    ctx.data["accounts"] = accounts
                    ctx.data["last_session_refresh"] = time.time()
                    try:
                        deps._save_session(ctx)
                    except RuntimeError as exc:
                        return deps._json_error(str(exc), 503)

                    try:
                        deps._save_session(ctx)
                    except RuntimeError as exc:
                        return deps._json_error(str(exc), 503)

                    try:
                        deps.notify(
                            f"🚀 新用户登录\n账号: {identifier}\n模式: {login_type}\n品牌: {sub_brand}\n当前共 {len(accounts)} 个账号",
                        )
                    except Exception:
                        logger.warning(
                            "login notify failed identifier=%s",
                            identifier,
                            exc_info=True,
                        )

                    return deps._json_success(
                        {"status": "success", "redirect": f"/main/{identifier}"}
                    )

            return deps._json_error("登录失败，请检查密码或OTP", 401)
        except Exception as exc:
            logger.exception(
                "login failed identifier=%s login_type=%s", identifier, login_type
            )
            return deps._json_error(str(exc), 500)
