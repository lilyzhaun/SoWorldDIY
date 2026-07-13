"""Auth helpers for brand lookup payloads and session account records."""

from __future__ import annotations

from typing import Any, Literal

LoginType = Literal["password", "otp"] | str


def resolve_login_url_and_brand(
    *,
    login_type: str,
    dipped_sub_brand: str,
    password_login_url: str,
    otp_login_url_for_brand: str,
) -> tuple[str, str]:
    """Return (login_url, sub_brand) for the chosen login mode.

    Password login always forces brand THREE and the THREE login URL, matching
    historical upstream behavior.
    """
    if login_type == "password":
        return password_login_url, "THREE"
    return otp_login_url_for_brand, dipped_sub_brand


def build_login_payload(
    *,
    login_type: str,
    identifier: str,
    password: str | None,
    otp: str | None,
) -> dict[str, Any]:
    """Build the upstream login JSON body."""
    payload: dict[str, Any] = {"id": identifier}
    if login_type == "password":
        payload["password"] = password
        payload["rememberMe"] = True
    else:
        payload["otp"] = otp
        payload["rememberMe"] = "true"
    return payload


def build_account_session_record(
    *,
    cookies: dict[str, Any],
    sub_brand: str,
    auth_code: str,
    login_type: str,
    password: str | None,
    otp: str | None,
    encrypted_password: str | None,
) -> dict[str, Any]:
    """Build the per-account session entry stored after successful login."""
    credential = password if login_type == "password" else f"OTP: {otp}"
    return {
        "cookies": cookies,
        "sub_brand": sub_brand,
        "auth_code": auth_code,
        "credential": credential,
        "login_type": login_type,
        "stored_password_encrypted": encrypted_password
        if login_type == "password"
        else None,
    }


def format_login_notify_message(
    *,
    identifier: str,
    login_type: str,
    sub_brand: str,
    account_count: int,
) -> str:
    """Format the admin notify string for a successful login."""
    return (
        f"🚀 新用户登录\n账号: {identifier}\n模式: {login_type}\n"
        f"品牌: {sub_brand}\n当前共 {account_count} 个账号"
    )
