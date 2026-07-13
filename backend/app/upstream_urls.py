"""Centralized upstream URL builders for SIMWorld and 3HK account-pro APIs."""

from __future__ import annotations

from typing import Final

SIMWORLD_API_BASE: Final[str] = "https://simworld.net/SIMworldApi-pro/HTHK/THREE"
THREE_ACCOUNT_BASE: Final[str] = "https://www.three.com.hk/account-pro/HTHK/THREE"
THREE_ACCOUNT_PRO_ROOT: Final[str] = "https://www.three.com.hk/account-pro"
SIMWORLD_WEB_MAIN: Final[str] = "https://simworld.net/SIMworld/main/tc"
SIMWORLD_PAYMENT_FINISHED: Final[str] = (
    "https://simworld.net/SIMworld/main/checkout/payment/finished/"
)
THREE_EXISTING_CUST_DIPPING: Final[str] = (
    f"{THREE_ACCOUNT_PRO_ROOT}/user/existingCustDipping"
)
THREE_DIY_PAYMENT_FINISHED: Final[str] = (
    "https://www.three.com.hk/prepaid/DIY/tc/checkout/payment/finished"
    "?actionflow=NEWSIM&purchaseid={purchaseid}"
)


def simworld_url(brand: str, *path_parts: str) -> str:
    """Build a SIMWorld API URL: ``{SIMWORLD_API_BASE}/{brand}/{path...}``."""
    if not path_parts:
        return f"{SIMWORLD_API_BASE}/{brand}"
    suffix = "/".join(path_parts)
    return f"{SIMWORLD_API_BASE}/{brand}/{suffix}"


def three_offer_url(brand: str, *path_parts: str) -> str:
    """Build a 3HK account-pro offer URL under HTHK/THREE/{brand}/..."""
    if not path_parts:
        return f"{THREE_ACCOUNT_BASE}/{brand}"
    suffix = "/".join(path_parts)
    return f"{THREE_ACCOUNT_BASE}/{brand}/{suffix}"
